# MetroMind eval report

Provider: **offline** · questions: 23 (20 answerable) · k = 5

### Retrieval

| chunking | chunks | retrieval | hit@1 | hit@5 | MRR |
|---|---|---|---|---|---|
| fixed | 7 | keyword | 1.00 | 1.00 | 1.00 |
| fixed | 7 | vector | 0.70 | 1.00 | 0.79 |
| fixed | 7 | hybrid | 0.80 | 1.00 | 0.90 |
| fixed | 7 | hybrid+hyde | 0.80 | 1.00 | 0.90 |
| recursive | 7 | keyword | 1.00 | 1.00 | 1.00 |
| recursive | 7 | vector | 0.70 | 1.00 | 0.79 |
| recursive | 7 | hybrid | 0.80 | 1.00 | 0.90 |
| recursive | 7 | hybrid+hyde | 0.80 | 1.00 | 0.90 |
| sentence | 21 | keyword | 1.00 | 1.00 | 1.00 |
| sentence | 21 | vector | 0.60 | 0.80 | 0.68 |
| sentence | 21 | hybrid | 0.75 | 1.00 | 0.83 |
| sentence | 21 | hybrid+hyde | 0.75 | 1.00 | 0.83 |

### Answers

| chunking | retrieval | accuracy | refusal | faithfulness | latency_s |
|---|---|---|---|---|---|
| fixed | keyword | 0.70 | 0.67 | 0.95 | 0.00 |
| fixed | vector | 0.70 | 0.67 | 0.95 | 0.00 |
| fixed | hybrid | 0.70 | 0.67 | 0.95 | 0.00 |
| fixed | hybrid+hyde | 0.70 | 0.67 | 0.95 | 0.00 |
| recursive | keyword | 0.65 | 0.67 | 0.80 | 0.00 |
| recursive | vector | 0.65 | 0.67 | 0.80 | 0.00 |
| recursive | hybrid | 0.65 | 0.67 | 0.80 | 0.00 |
| recursive | hybrid+hyde | 0.65 | 0.67 | 0.80 | 0.00 |
| sentence | keyword | 0.55 | 0.67 | 0.95 | 0.00 |
| sentence | vector | 0.55 | 1.00 | 0.75 | 0.00 |
| sentence | hybrid | 0.60 | 0.67 | 0.95 | 0.00 |
| sentence | hybrid+hyde | 0.60 | 0.67 | 0.95 | 0.00 |
