# Guía de puesta en marcha

Este repo genera cada lunes una lista de empleos junior de biología computacional
y bioinformática en el Reino Unido, tomados directamente de las webs de empleo de
cada empresa, y marca las que figuran en el registro de patrocinadores de visa del
Home Office (ruta Skilled Worker).

## 1. Subirlo a GitHub (10 minutos)

1. Crea un repositorio nuevo y público en GitHub, por ejemplo
   `Entry-Level-Computational-Biology-Jobs-UK`.
2. Sube todo el contenido de esta carpeta (incluida la carpeta oculta `.github`).
   Desde la terminal:
   ```bash
   cd uk-compbio-jobs
   git init && git add . && git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
   git push -u origin main
   ```
   Si lo subes desde la web ("Add file → Upload files"), asegúrate de que el
   archivo `.github/workflows/weekly.yml` llega con esa misma ruta.
3. En el repo: **Settings → Actions → General → Workflow permissions** y elige
   **Read and write permissions**. Sin esto el Action no puede guardar el README.
4. Ve a la pestaña **Actions**, abre "Weekly rebuild" y pulsa **Run workflow**
   para la primera ejecución. A partir de ahí se ejecuta solo cada lunes.

## 2. Comprobar qué empresas funcionan

Las direcciones de las webs de empleo en `config/config.yaml` son un punto de partida:
las empresas cambian de proveedor a veces. En tu ordenador:

```bash
conda env create -f environment/environment.yml
conda activate uk-compbio-jobs
python -m jobsbot check
```

(`requirements.txt` es el mismo listado de paquetes; lo usa el GitHub Action.)

Verás una tabla con cada empresa, si respondió, cuántas ofertas trajo, cuántas
están en el Reino Unido y cuántas pasan el filtro. Si alguna da `ERROR`, corrige
su identificador o ponle `disabled: true`.

## 3. Añadir empresas

Abre la página de empleo de la empresa y pulsa en una oferta. La dirección del
botón "Apply" te dice qué sistema usa:

| Si la dirección contiene | Pon en config.yaml |
| --- | --- |
| `boards.greenhouse.io/XXX` o `job-boards.greenhouse.io/XXX` | `ats: greenhouse`, `slug: XXX` |
| `jobs.lever.co/XXX` | `ats: lever`, `slug: XXX` |
| `jobs.eu.lever.co/XXX` | `ats: lever`, `slug: XXX`, `region: eu` |
| `jobs.ashbyhq.com/XXX` | `ats: ashby`, `slug: XXX` |
| `XXX.wd3.myworkdayjobs.com/SITIO` | `ats: workday`, `host: XXX.wd3.myworkdayjobs.com`, `tenant: XXX`, `site: SITIO` |
| `jobs.smartrecruiters.com/XXX` | `ats: smartrecruiters`, `slug: XXX` |

Para universidades e institutos (Sanger, Crick, EMBL-EBI, Oxford, Cambridge…)
lo más práctico es jobs.ac.uk: haz una búsqueda, copia el enlace RSS de la página
de resultados y pégalo en la entrada `jobs.ac.uk` de `config/config.yaml` (quita
`disabled: true`). Puedes añadir una entrada por cada búsqueda.

Si una empresa patrocina visas pero no sale marcada, busca su nombre legal en el
[registro](https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers)
y añádelo en `sponsor_names`.

## 4. Ajustar los filtros

Todo está en `config/config.yaml`:

- `exclude_titles`: palabras que descartan una oferta (senior, lead, manager…).
- `categories`: las listas temáticas y sus palabras clave.
- `early_career_keywords`: qué cuenta como graduate scheme, prácticas o placement.
- `max_age_days`: descarta ofertas más antiguas que esto.

Las palabras clave son expresiones regulares: `\w*` significa "cualquier
terminación", así `bioinformatic\w*` encaja con bioinformatics y bioinformatician.

## 5. Ejecutar las pruebas

```bash
python -m pytest -q
```

El Action ejecuta las pruebas antes de cada actualización, así que un cambio que
rompa algo no llega a publicarse.

## Notas

- Solo se usan las APIs públicas que las propias empresas exponen para su web de
  empleo; no se copia nada de LinkedIn ni Indeed.
- Estar en el registro del Home Office significa que la empresa *puede*
  patrocinar, no que lo haga para cada puesto. Además, el puesto debe superar el
  umbral salarial de la visa Skilled Worker.
- `data/first_seen.json` guarda la fecha en que se vio cada oferta por primera
  vez; se usa cuando la web de empleo no indica fecha de publicación.
