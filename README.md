# junction-hsy-valmet-challenge

## Installation and running

Use make to install and run app

```bash

# Install deps with pip
make install

# Run the simulationa
make run

# Run QA (lint, format, tc)
make qa

```

You can run the validation script with:

```bash
python -m validate_run simulation_output_23_47_52.csv
```

Or just:

```bash
python -m validate_run
```

And this will run validation on the benchmark data file "Hackathon_HSY_data.csv".
