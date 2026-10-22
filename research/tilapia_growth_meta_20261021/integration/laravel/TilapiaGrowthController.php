<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;

class TilapiaGrowthController extends Controller
{
    public function index(Request $request)
    {
        $input = $request->validate(['piscina_id' => ['nullable', 'integer', 'min:1']]);
        return view('tilapia-growth', ['pond' => (int) ($input['piscina_id'] ?? 1)]);
    }

    public function data(Request $request)
    {
        $input = $request->validate(['piscina_id' => ['nullable', 'integer', 'min:1']]);
        $pond = (int) ($input['piscina_id'] ?? 1);
        $keyPath = storage_path('app/private/tilapia-growth-api.key');
        if (!is_readable($keyPath)) {
            return response()->json(['message' => 'El servicio ML todavía no está configurado.'], 503);
        }
        $key = trim(file_get_contents($keyPath));
        $base = rtrim(config('services.tilapia_growth.url', 'http://aquaculture_backend:8013/api/v1'), '/');
        try {
            $forecasts = [];
            foreach ([7, 14, 28] as $days) {
                $r = Http::acceptJson()->withToken($key)->connectTimeout(3)->timeout(12)
                    ->get("{$base}/ponds/{$pond}/models/tilapia-growth-adaptive/forecast", ['projection_days' => $days]);
                if ($r->failed()) {
                    return response()->json(['message' => 'No hay una proyección disponible para esta piscina. Verifica sus biometrías o el servicio ML.'], 503);
                }
                $forecasts[] = $r->json();
            }
            $intervalContext = null;
            try {
                $comparison = Http::acceptJson()->withToken($key)->connectTimeout(3)->timeout(5)
                    ->get("{$base}/models/tilapia-growth-interval-context/status");
                if ($comparison->successful() && (int) $comparison->json('pond_id') === $pond) {
                    $intervalContext = $comparison->json();
                }
            } catch (\Throwable $e) {
                // A diagnostic comparison must not prevent the existing projection.
            }
            return response()->json(['forecasts' => $forecasts, 'interval_context' => $intervalContext])
                ->header('Cache-Control', 'no-store');
        } catch (\Throwable $e) {
            return response()->json(['message' => 'El servicio de crecimiento ML no está disponible. Intenta nuevamente.'], 503);
        }
    }
}
