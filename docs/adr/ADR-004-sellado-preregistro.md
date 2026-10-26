# ADR-004 · Sellado del preregistro (tag git + sello externo)

**Fecha:** 2026-10-26 · **Estado:** aceptado (M0); sello externo pendiente de
credenciales/decisión del usuario.

## Contexto

El preregistro solo vale si puede probarse que existía **antes** de ver los
resultados. El prompt pide tag git firmado `prereg-v1` + hash del documento +
sugerir sello externo. El entorno no tiene `gpg` (verificado 2026-10-26), así
que la firma GPG del tag es imposible aquí; además, un repo git local/privado
es reescribible por su propio dueño: el tag prueba poco frente a un escéptico.

## Decisión

1. **Tag anotado `prereg-v1`** sobre el commit que congela
   `docs/PREREGISTRO.md` + `config/hypotheses.yaml` v1.0. El mensaje del tag
   incluye el **SHA256** de ambos ficheros (doble anclaje: hash del commit +
   hash de contenido).
2. **Sello externo recomendado: OSF Registrations** (https://osf.io):
   registro gratuito del documento (markdown/PDF) que produce un timestamp de
   tercero, inmutable y público. Alternativa equivalente: **OpenTimestamps**
   (ancla el hash en Bitcoin) o publicar el hash en un medio fechado
   (p. ej., un gist público + fecha, o el propio issue tracker).
   Por qué importa: OSF/OpenTimestamps usan un reloj y un almacén que **no
   controlamos**; eso convierte "registramos la hipótesis antes" en un hecho
   verificable por cualquiera, no en una promesa.
3. **Procedimiento cuando haya acceso:** exportar el PDF de PREREGISTRO v1.0 →
   subir a OSF → guardar el DOI/URL de la registro en `docs/evidence/` y
   añadirlo a este ADR (addendum fechado). Hasta entonces:
   `[SELLO EXTERNO PENDIENTE]`.
4. Cualquier versión nueva del preregistro (v1.1+) repite el proceso: tag
   `prereg-v1.1`, hashes, sello externo. Las versiones nunca se borran.

## Alternativas descartadas

- Firmar con una clave GPG autogenerada en el sandbox: autofirma sin
  confianza externa; teatro de seguridad.
- Confiar solo en la fecha del commit git: reescribible (`git commit
  --amend`, filtros de fecha); no prueba nada ante terceros.
- Notario humano: fuera del alcance y más lento que OSF.

## Consecuencias

- El tag `prereg-v1` de M0 es anotado, no firmado: desviación declarada en el
  informe M0 y mitigada por el hash de contenido + sello externo en cuanto el
  usuario lo autorice (no bloquea la investigación; bloquea *afirmar* que el
  preregistro es a prueba de manipulación).
