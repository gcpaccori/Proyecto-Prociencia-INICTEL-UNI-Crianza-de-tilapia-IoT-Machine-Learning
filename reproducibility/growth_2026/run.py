#!/usr/bin/env python3
"""Reproduce the SISMAPISCIS October 2026 growth chart from curated evidence.

Scientific scope: a retrospective, end-of-interval comparison on one campaign.
The Ridge and GP implementations are imported from original_ml_core.py;
neither their coefficients nor their predictions are hard-coded here.
No databases, deployment endpoints, external network or secrets are used.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
from pathlib import Path

from original_ml_core import evaluate, metrics, VARIANTS

BASE = Path(__file__).resolve().parent
T0_C = 15.5                        # Original mechanistic TGC code, 2026-09-30
W_INF_G = 392.32                  # Original VBGF code, 2026-09-30
TREF_EFF_C = 13.245267797152454  # Original Seed -> B1 thermal calibration
OD_LOW_RATIO = ((1.24 / 1.75) + (2.99 / 4.23)) / 2
MIN_COVERAGE = .70
COLORS = {
    "observed": "#1268ac", "tgc": "#f07819", "vbgf": "#208a55",
    "ridge": "#c62a36", "gp": "#8c52b9",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def oxygen_factor(oxygen_mean: float) -> float:
    """Tran-Duy Table 2 interpolation used in archived TGC/VBGF variants."""
    if oxygen_mean <= 3.0:
        return OD_LOW_RATIO
    if oxygen_mean >= 5.5:
        return 1.0
    return OD_LOW_RATIO + (1.0 - OD_LOW_RATIO) * (oxygen_mean - 3.0) / 2.5


def calculate_references(rows: list, biometries: list) -> list:
    """One-step TGC/VBGF nowcasts; coefficients use only preceding intervals.

    At evaluation i, B_i is the observed start weight. Known previous weights
    may determine C and K. The target's W_i+1 is NEVER used to fit them.
    Temperature and OD are retrospectively available only after the interval.
    """
    weights = [float(b["mean_g"]) for b in biometries]
    roots = [w ** (1.0 / 3.0) for w in weights]
    asymptote = W_INF_G ** (1.0 / 3.0)
    exposure = []
    for i, row in enumerate(rows):
        feat = row["features"]
        qc = row["quality"]
        for variable in ("temperature", "oxygen", "ph"):
            if not qc["eligible"] or qc["coverage"][variable] < MIN_COVERAGE:
                raise ValueError(f"Ineligible {row['target']} / {variable}")
        if row["anchor"] != biometries[i]["date"] or row["target"] != biometries[i+1]["date"]:
            raise ValueError("Chronological biometries do not match intervals")
        if not math.isclose(float(row["actual_weight_g"]), weights[i+1], abs_tol=1e-7):
            raise ValueError("Observed end weight inconsistent with biometric sample")
        if not math.isclose(float(row["initial_weight_g"]), weights[i], abs_tol=1e-7):
            raise ValueError("Observed initial weight inconsistent with biometric sample")
        duration = float(feat["duration_days"])
        if duration <= 0:
            raise ValueError("Nonpositive interval duration")
        exposure.append(
            duration * max(float(feat["temperature_mean"]) - T0_C, 0)
            * oxygen_factor(float(feat["oxygen_mean"]))
        )

    results = []
    for i in range(2, len(rows)):  # min 2 preceding intervals, same as ML
        # Only B1 -> B_i exposure enters calibration: no current-interval data.
        previous_exposure = sum(exposure[:i])
        if previous_exposure <= 0 or roots[i] >= asymptote:
            raise ValueError("Unsupported mechanistic calibration")
        c_tgc = (roots[i] - roots[0]) / previous_exposure
        k_vbgf = -math.log(
            (asymptote - roots[i]) / (asymptote - roots[0])
        ) / (previous_exposure / TREF_EFF_C)
        target_exposure = exposure[i]
        tgc_pred = (roots[i] + c_tgc * target_exposure) ** 3
        vbgf_pred = (
            asymptote - (asymptote - roots[i])
            * math.exp(-k_vbgf * target_exposure / TREF_EFF_C)
        ) ** 3
        results.append({
            "target": rows[i]["target"],
            "anchor": rows[i]["anchor"],
            "n_training_intervals": i,
            "training_last_target": rows[i-1]["target"],
            "tgc_weight_g": tgc_pred, "vbgf_weight_g": vbgf_pred,
            "tgc_coefficient": c_tgc, "vbgf_k_per_day": k_vbgf,
            "target_interval_thermal_oxygen_exposure": target_exposure,
            "target_interval_oxygen_factor": oxygen_factor(
                float(rows[i]["features"]["oxygen_mean"])
            ),
        })
    return results


def run_analysis() -> tuple[list, dict, list]:
    cohort = json.loads((BASE / "cohort.json").read_text())
    reference = json.loads((BASE / "reference_replay.json").read_text())
    rows = cohort["intervals"]
    biometric = cohort["biometries"]
    if len(rows) != 6 or len(biometric) != 7:
        raise ValueError("Expected six intervals and seven observed biometries")
    if cohort["time_axis"] != "receipt_available / created_at (America/Lima)":
        raise ValueError("Unexpected input clock")
    stats = {b["id"]: {"sd_g": b["sd_g"], "n": b["n"]} for b in biometric}
    tgc_vbgf = calculate_references(rows, biometric)
    # REAL core invocation: re-fit Ridge and GP on each past-only training prefix.
    ridge = evaluate(rows, stats, "ridge_correlated", VARIANTS["water_means"])
    gp = evaluate(rows, stats, "gaussian_correlated", VARIANTS["exposure"])
    assert len(ridge) == len(gp) == len(tgc_vbgf) == 4
    joined = []
    for mech, r, g in zip(tgc_vbgf, ridge, gp):
        if not (mech["target"] == r["target"] == g["target"]):
            raise ValueError("ML and mechanistic evaluation dates do not align")
        if not (r["n_training_intervals"] == g["n_training_intervals"] == mech["n_training_intervals"]):
            raise ValueError("ML and mechanistic training prefixes differ")
        if not (r["training_last_target"] == g["training_last_target"] == mech["training_last_target"]):
            raise ValueError("Future labels detected in model training")
        # Archived Oct 25 replay serves as an independent checksum / regression test.
        for family, variant, got in (
            ("ridge_correlated", "water_means", r["predicted_weight_g"]),
            ("gaussian_correlated", "exposure", g["predicted_weight_g"]),
        ):
            match = [v for v in reference["predictions"]
                     if (v["date"], v["family"], v["variant"]) ==
                     (mech["target"], family, variant)]
            if len(match) != 1 or abs(match[0]["predicted_weight_g"] - got) > 1e-3:
                raise ValueError(f"ML replay disagreement: {family} / {mech['target']}")
        joined.append({
            "date": mech["target"], "anchor": mech["anchor"],
            "n_training_intervals": mech["n_training_intervals"],
            "training_last_target": mech["training_last_target"],
            "weight_observed_g": float(r["actual_weight_g"]),
            "tgc_g": mech["tgc_weight_g"], "vbgf_g": mech["vbgf_weight_g"],
            "ridge_g": float(r["predicted_weight_g"]),
            "gaussian_g": float(g["predicted_weight_g"]),
            "tgc_coefficient": mech["tgc_coefficient"],
            "vbgf_k_per_day": mech["vbgf_k_per_day"],
            "target_interval_thermal_oxygen_exposure": mech["target_interval_thermal_oxygen_exposure"],
            "target_interval_oxygen_factor": mech["target_interval_oxygen_factor"],
            "sensor_coverage": rows[mech["n_training_intervals"]]["quality"]["coverage"],
            "ridge_outside_training_features": r["outside_training_features"],
            "gaussian_outside_training_features": g["outside_training_features"],
        })

    score = {}
    for k in ("tgc", "vbgf", "ridge", "gaussian"):
        errors = [r[k+"_g"] - r["weight_observed_g"] for r in joined]
        score[k] = {
            "MAE_g": sum(abs(v) for v in errors) / len(errors),
            "RMSE_g": math.sqrt(sum(v*v for v in errors) / len(errors)),
            "bias_g": sum(errors) / len(errors),
            "max_error_g": max(abs(v) for v in errors),
            "n_dates": len(errors),
        }
    return joined, score, biometric


def svg_chart(rows: list, biometric: list, score: dict, path: Path):
    """Pure-stdlib, publication-quality vector capture; no plot dependency."""
    w, h = 1480, 880
    L, R, T, B = 110, 45, 200, 115
    plot_w, plot_h = w-L-R, h-T-B
    ymax = 205
    x = lambda i: L + plot_w * i/6
    y = lambda val: T + plot_h*(1-val/ymax)
    labels = [b["date"][8:10]+"/"+b["date"][5:7] for b in biometric]
    series = {
        "observed": [float(b["mean_g"]) for b in biometric],
        "tgc": [None,None,float(biometric[2]["mean_g"])]+[r["tgc_g"] for r in rows],
        "vbgf": [None,None,float(biometric[2]["mean_g"])]+[r["vbgf_g"] for r in rows],
        "ridge": [None,None,None]+[r["ridge_g"] for r in rows],
        "gp": [None,None,None]+[r["gaussian_g"] for r in rows],
    }
    names = {
        "observed":"Peso observado","tgc":"TGC generalizado · recalibrado",
        "vbgf":"Von Bertalanffy · recalibrado",
        "ridge":"Modelo SISMAPISCIS · Ridge",
        "gp":"Modelo probabilístico SISMAPISCIS · gaussiano",
    }
    shapes = []
    def add(s): shapes.append(s)
    def tx(px,py,s,size=19,fill="#344458",anchor="start",weight="normal"):
        add(f'<text x="{px}" y="{py}" font-family="DejaVu Sans,Arial,sans-serif" font-size="{size}" text-anchor="{anchor}" fill="{fill}" font-weight="{weight}">{html.escape(str(s))}</text>')
    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">')
    add('<rect width="100%" height="100%" fill="white"/>')
    tx(w//2,45,"SISMAPISCIS | Comparación de modelos de crecimiento",33,"#101826","middle","bold")
    tx(w//2,81,"Calibración con intervalos previos · evaluación cronológica retrospectiva",19,"#607086","middle")
    for i,(name,key) in enumerate([(names[k],k) for k in series]):
        px=115 + (i%3)*440; py=120 +(i//3)*34
        add(f'<line x1="{px}" y1="{py-5}" x2="{px+36}" y2="{py-5}" stroke="{COLORS[key]}" stroke-width="4"/>')
        add(f'<circle cx="{px+18}" cy="{py-5}" r="6" fill="{COLORS[key]}"/>')
        tx(px+46,py+2,name,17,"#243143")
    add(f'<rect x="{L}" y="{T}" width="{x(2.5)-L}" height="{plot_h}" fill="#f0f3f7"/>')
    add(f'<line x1="{x(2.5)}" y1="{T}" x2="{x(2.5)}" y2="{T+plot_h}" stroke="#97a5b6" stroke-dasharray="7,5" stroke-width="2"/>')
    for val in range(0,201,25):
        yy=y(val);add(f'<line x1="{L}" x2="{w-R}" y1="{yy}" y2="{yy}" stroke="#e2e7ed"/>')
        tx(L-14,yy+6,val,17,"#273549","end")
    for i,label in enumerate(labels):
        add(f'<line x1="{x(i)}" x2="{x(i)}" y1="{T}" y2="{T+plot_h}" stroke="#edf0f4"/>')
        tx(x(i),T+plot_h+32,label,18,"#22303e","middle")
    tx(x(1),T+35,"CALIBRACIÓN INICIAL · 3 BIOMETRÍAS",17,"#566983","middle","bold")
    tx(x(4.35),T+35,"EVALUACIÓN CRONOLÓGICA · 4 FECHAS",17,"#566983","middle","bold")
    for key, arr in series.items():
        valid=[(i,val) for i,val in enumerate(arr) if val is not None]
        points=" ".join(f"{x(i):.2f},{y(val):.2f}" for i,val in valid)
        dash=' stroke-dasharray="10,8"' if key in ("tgc","vbgf") else (' stroke-dasharray="2,8"' if key in ("ridge","gp") else '')
        add(f'<polyline points="{points}" fill="none" stroke="{COLORS[key]}" stroke-width="4"{dash}/>')
        for i,val in valid:
            add(f'<circle cx="{x(i):.2f}" cy="{y(val):.2f}" r="7" fill="{COLORS[key]}" stroke="white" stroke-width="1.6"/>')
    tx(w//2, h-59,"Fecha de biometría / evaluación (2026)",19,"#283447","middle")
    tx(26,T+plot_h/2,"Peso promedio (g)",19,"#283447","middle")
    # Keep long text strictly below the plot area.
    metrics_line="MAE (g):  TGC {:.2f}   |   VBGF {:.2f}   |   Ridge {:.2f}   |   Gaussiano {:.2f}".format(
        score["tgc"]["MAE_g"],score["vbgf"]["MAE_g"],score["ridge"]["MAE_g"],score["gaussian"]["MAE_g"])
    tx(w//2,h-26,metrics_line,17,"#101826","middle","bold")
    add("</svg>")
    path.write_text("\n".join(shapes)+"\n")


def optional_png(rows: list, biometric: list, out: Path):
    """If matplotlib is installed, also write a lossless PNG screenshot."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    xx = list(range(len(biometric)))
    observed = [b["mean_g"] for b in biometric]
    specs = [
        ("Peso observado", observed, COLORS["observed"], "-", "o"),
        ("TGC generalizado · recalibrado", [None,None,observed[2]]+[r["tgc_g"] for r in rows], COLORS["tgc"], "--","s"),
        ("Von Bertalanffy · recalibrado", [None,None,observed[2]]+[r["vbgf_g"] for r in rows], COLORS["vbgf"],"--","^"),
        ("SISMAPISCIS · Ridge", [None]*3+[r["ridge_g"] for r in rows], COLORS["ridge"],":","D"),
        ("SISMAPISCIS · Gaussiano", [None]*3+[r["gaussian_g"] for r in rows], COLORS["gp"],":","P"),
    ]
    fig,ax=plt.subplots(figsize=(13,7.7))
    ax.axvspan(-.3,2.48,color="#f0f3f7")
    ax.axvline(2.5,color="#98a8ba",ls="--")
    for name, values,color,ls,marker in specs:
        ax.plot(xx,values,color=color,linestyle=ls,marker=marker,linewidth=2.5,markersize=7,label=name)
    ax.set_xticks(xx,[b["date"][8:10]+"/"+b["date"][5:7] for b in biometric])
    ax.set_ylim(0,205)
    ax.set_ylabel("Peso promedio de tilapia (g)")
    ax.set_xlabel("Fecha de biometría / evaluación (2026)")
    ax.set_title("SISMAPISCIS | Comparación cronológica de modelos de crecimiento",fontsize=17,weight="bold")
    ax.legend(loc="upper left",ncol=2,fontsize=9)
    ax.grid(alpha=.18)
    fig.tight_layout()
    fig.savefig(out,dpi=200)
    plt.close(fig)
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,default=BASE/"evidence",help="Output directory; no database writes")
    args=parser.parse_args()
    rows,score,biometric=run_analysis()
    out=args.out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    columns=["date","anchor","n_training_intervals","weight_observed_g","tgc_g","vbgf_g","ridge_g","gaussian_g",
             "tgc_coefficient","vbgf_k_per_day","target_interval_thermal_oxygen_exposure","target_interval_oxygen_factor"]
    with (out/"predictions.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=columns,extrasaction="ignore")
        writer.writeheader();writer.writerows(rows)
    audit={"protocol":"one-step retrospective end-of-interval, training prefixes 2/3/4/5, sensors observed at end",
           "source_clock":"receipt_available / created_at, America/Lima",
           "biometric_sample_dates":[b["date"] for b in biometric],
           "mathematical_formulas":{
               "TGC":"W_next = (W_anchor^(1/3) + C_prefix * E_target) ^ 3",
               "VBGF":"W_next = (A-(A-W_anchor^(1/3))*exp(-K_prefix * E_target/TREF))^3",
               "E_target":"days * max(T_mean-15.5,0) * f_OD(oxygen_mean)",
               "C_prefix":"(W_anchor^(1/3)-W_B1^(1/3))/SUM(E_previous)",
               "K_prefix":"-log((A-W_anchor^(1/3))/(A-W_B1^(1/3)))/(SUM(E_previous)/TREF)",
               "reference":"archived mechanical models 2026-09-30, re-fit chronological adaptation",
               "oxygen_low_ratio":OD_LOW_RATIO,"T0_C":T0_C,"W_inf_g":W_INF_G,"TREF_C":TREF_EFF_C,
               "sensor_aggregation_note":"hourly exposure approximated using eligible interval means, not raw daily T/OD"
           },
           "ml_calls":[
               "original_ml_core.evaluate(rows,biometry_stats,'ridge_correlated',VARIANTS['water_means'])",
               "original_ml_core.evaluate(rows,biometry_stats,'gaussian_correlated',VARIANTS['exposure'])"],
           "metrics":score,"rows":rows,
           "limitations":["one known campaign","development labels also used for method selection",
                          "conditional GP dispersion is not calibrated","not forecast from interval start",
                          "physical timing of sensor exposure not independently verified"]}
    (out/"audit.json").write_text(json.dumps(audit,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
    svg_chart(rows,biometric,score,out/"chart.svg")
    png_made=optional_png(rows,biometric,out/"chart.png")
    files=["cohort.json","reference_replay.json","original_ml_core.py","run.py"]
    manifest={"runner":"SISMAPISCIS 2026-11-06 reproducible growth comparison",
              "dataset_sha256":{p:sha256(BASE/p) for p in files},
              "outputs_sha256":{p:sha256(out/p) for p in ["predictions.csv","audit.json","chart.svg"]+(['chart.png'] if png_made else [])},
              "result_verified_against_historical_ml_replay":True,
              "no_db_write":True,"no_automatic_deployment":True}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"status":"PASS","dates":[r["date"] for r in rows],
          "MAE_g":{k:round(v["MAE_g"],3) for k,v in score.items()},
          "last_date":{k:round(rows[-1][k+"_g"],3) for k in ("tgc","vbgf","ridge","gaussian")},
          "png":png_made,"out":str(out)},ensure_ascii=False))
if __name__=="__main__":
    main()
