# Gemelo Digital Productivo RAS

## Objetivo

El modulo debe representar el estado actual de cada piscina, proyectar su continuidad y comparar escenarios operativos de 1 dia, 7 dias y 30 dias. Debe integrar calidad de agua, poblacion, biomasa, crecimiento, alimentacion, comportamiento, riesgos y modelos disponibles.

## Separacion obligatoria de evidencia

- **Medido:** oxigeno disuelto, temperatura, pH y nitrato obtenidos desde `clean_measurements`.
- **Configurado por el productor:** numero de peces, peso promedio, talla, volumen de agua, aireacion, filtracion, alimento, FCR y eventos operativos.
- **Calculado con formula documentada:** biomasa, crecimiento lineal Soderberg, relacion peso-longitud de tilapia del Nilo y racion Haskell.
- **Indice operativo simulado:** claridad/suciedad, apetito, estres, exposicion a enfermedad y riesgo de mortalidad. No debe presentarse como medicion ni mortalidad confirmada.

## Mandos RAS con impacto

Los controles deben modificar inmediatamente la escena y volver a ejecutar el escenario:

| Control | Efecto visual | Efecto simulado |
|---|---|---|
| Numero de peces | Densidad visible | Biomasa y carga |
| Peso y talla inicial | Tamano relativo | Crecimiento, biomasa y racion |
| Volumen de agua | Densidad y capacidad | kg/m3 |
| Aireacion | Burbujas y actividad | Supuesto explicito de cambio de OD |
| Filtracion | Particulas y claridad | Supuesto explicito de reduccion de carga |
| Alimentacion | Peces acuden al alimento | Racion, carga y alimento acumulado |
| Limpieza/sifonado | Reduccion visual de residuos | Reinicio parcial del indice de carga |

## Estado biologico y productivo

Cada punto temporal debe devolver:

- cantidad de peces;
- peso promedio y longitud;
- biomasa total y densidad kg/m3;
- ganancia diaria;
- racion diaria y alimento acumulado;
- FCR configurado;
- indice de calidad de agua, apetito, estres, suciedad y riesgo;
- comportamiento esperado: normal, alimentandose, estresado, enfermo o riesgo critico.

## Simulacion multivariable

El usuario debe poder comparar:

1. continuidad con tendencia real;
2. escenario hipotetico con cambios de sensores;
3. cambios RAS de aireacion, filtracion, poblacion y alimento;
4. horizonte de 24 horas, 7 dias o 30 dias;
5. participacion y disponibilidad de modelos.

La proyeccion debe conservar las entradas, supuestos, formulas, procedencia y advertencias. Los coeficientes operativos no documentados deben mostrarse como supuestos editables, nunca como formulas cientificas validadas.

## Comportamiento visual

- Los peces nadan con trayectorias y velocidades independientes.
- Al registrar alimentacion, los peces convergen temporalmente hacia el alimento.
- Con estres aumenta la velocidad irregular y cambia el color.
- Con criticidad algunos peces representan riesgo de mortalidad, sin afirmar muerte real.
- El agua cambia de claridad y color segun el indice operativo derivado.
- Deben verse residuos, burbujas, corriente, sensores, alimentacion y limpieza.
- No debe existir un numero grande tapando el centro del estanque.

## Registro y trazabilidad

La interfaz debe mostrar eventos de alimentacion, limpieza, cambios de controles, ejecuciones y escenarios. Cada resultado debe identificar si proviene de MySQL, formula documentada o supuesto operativo.

## Criterio de terminado

El productor puede configurar la poblacion, observar el estado real, ejecutar escenarios de hasta 30 dias, comparar produccion y riesgo, entender que modelo participa y distinguir sin ambiguedad mediciones, calculos y simulaciones.
