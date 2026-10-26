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

## Addendum (M0b, 2026-10-26) — sellado ejecutado

1. **Firma SSH disponible y usada.** Se instaló `openssh-client` en el entorno
   y se generó una clave dedicada ed25519 de firma de preregistros:
   - Privada: `~/.ssh/qa_prereg_ed25519` (fuera del repo; NUNCA se commitea).
   - Pública: `docs/keys/prereg_signer_ed25519.pub` (committeada a propósito:
     cualquiera debe poder verificar).
   - `allowed_signers`: `~/.ssh/allowed_signers` con
     `quant-arena-prereg-signer@localhost`.
   - Tag **`prereg-v1-signed`** creado sobre el MISMO commit `82bf430`
     (prereg-v1 queda intacto). Verificación OK: `git tag -v
     prereg-v1-signed` → *Good "git" signature … ED25519 key
     SHA256:SyPjyq4EimJ2X48XuJRQgHiIh/5XFHYqhC/Sd86OyYQ*
     (evidencia: `docs/evidence/ssh_signature_log.txt`).
   - Alcance honesto: la firma SSH acredita *control de la clave del
     proyecto*, no identidad civil; el ancla de fecha externa la da
     OpenTimestamps. Verificar requiere `openssh-client` + el allowed_signers.
   - Nota de entorno: este sandbox NO persiste `.git/config` entre sesiones;
     `make git-config` re-aplica identidad y configuración de firma.
2. **OpenTimestamps ejecutado (P3: "ya").** `ots stamp` sobre
   `docs/evidence/normative_hashes_v1.0.txt` (contiene los SHA256 v1.0 de
   PREREGISTRO.md e hypotheses.yaml). Cuatro calendarios respondieron; estado
   inicial *Pending confirmation in Bitcoin blockchain* (el anclaje BTC tarda
   horas). Prueba: `normative_hashes_v1.0.txt.ots`; log:
   `ots_stamp_log_v1.0.txt`. **Checklist M1:** `make ots-check`
   (`ots upgrade` + `ots verify`) hasta obtener success con altura de bloque.
   Idéntico procedimiento para los hashes v1.1.
3. **OSF antes de M3 (P3):** el usuario crea la cuenta; se registrará el
   PREREGISTRO vigente + hashes y se añadirá aquí la URL/DOI de registro.
4. **Remoto git / CI:** se requiere que el usuario proporcione un remoto
   (p. ej. GitHub) con credenciales; instrucciones exactas en el informe M0b.
   Se realizó un push de prueba a un remoto-bare local para validar que ramas
   y tags viajan limpios.
