# 🧬 Entry Level Computational Biology & Bioinformatics Jobs — UK

---

## 📌 Overview

This repository contains a **weekly updated list of entry level computational biology, bioinformatics, biostatistics and biotech data science roles** in the United Kingdom, taken directly from employers' own careers sites.

> ⏳ The first build has not run yet. Go to **Actions → Weekly rebuild → Run workflow** to generate the lists. This README is then rewritten automatically every Monday.

---

## 🔁 Reproducibility

```bash
conda env create -f environment/environment.yml
conda activate uk-compbio-jobs
python -m jobsbot check    # test every employer's job board
python -m jobsbot build    # rebuild README, lists, CSV and JSON
```

Employers and filters: [`config/config.yaml`](config/config.yaml) · Setup guide (Spanish): [`docs/GUIA.md`](docs/GUIA.md)

---

*Maintained by [fatinataly](https://github.com/fatinataly) · bebioinformatician.*
