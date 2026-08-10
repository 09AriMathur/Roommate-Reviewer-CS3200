# Summer B 2026 CS 3200 Project Template

This is a template repo for Dr. Fontenot's Summer B 2026 CS 3200 Course Project.

It includes most of the infrastructure setup (containers), sample databases, and example UI pages. Explore it fully and ask questions!

## Prerequisites

See [docs/PreReq.md](docs/PreReq.md) for full setup instructions, including Python environment setup with Anaconda/Miniconda or the standard Python virtual environment tool, required tools, and IDE configuration.

A full index of the project documentation is in [docs/README.md](docs/README.md).

## Structure of the Repo

- This repository is organized into six main directories:
  - `./app` - the Streamlit app
  - `./api` - the Flask REST API
  - `./database-files` - SQL scripts to initialize the MySQL database
  - `./datasets` - folder for storing datasets
  - `./ml-src` - folder for ML model development (Jupyter notebooks, training scripts)
  - `./docs` - project documentation

- The repo also contains a `docker-compose.yaml` file that is used to set up the Docker containers for the front end app, the REST API, and MySQL database.

## Suggestion for Learning the Project Code Base

If you are not familiar with web app development, this code base might be confusing. But don't worry, we'll get through it together. Here are some suggestions for learning the code base:

1. Start by exploring the `./app` directory. This is where the Streamlit app is located. The Streamlit app is a Python-based web app that is used to interact with the user. It's a great way to build a simple web app without having to learn a lot of web development.
1. Next, explore the `./api` directory. This is where the Flask REST API is located. The REST API is used to interact with the database and perform other server-side tasks. You might also consider this the "application logic" or "business logic" layer of your app.
1. Finally, explore the `./database-files` directory. This is where the SQL scripts are located that will be used to initialize the MySQL database.
1. Bonus: If you want a totally separate copy of the template repo on your laptop to explore and experiment with without affecting your team repo, see the *Setting Up a Personal Sandbox Repo* section in [docs/RepoSetup.md](docs/RepoSetup.md).

## Setting Up the Repos

See [docs/RepoSetup.md](docs/RepoSetup.md) for full instructions on forking and configuring the team repo, setting up the `.env` file, and running the Docker containers. An optional section there also covers setting up a personal sandbox repo for individual experimentation.

## Important Tips

See [docs/ImportantTips.md](docs/ImportantTips.md) for tips on hot reloading, recovering from container crashes, and working with the MySQL container — including why you need the `-v` flag to pick up changes to your SQL files.

## Handling User Role Access and Control

This project uses a simple Role-based Access Control (RBAC) system implemented in Streamlit. The template ships with example roles (*Political Strategist*, *USAID Worker*, *System Administrator*) to illustrate the pattern — **your team will replace these with the personas specific to your project**. You will define four personas and implement three of them.

See [docs/RBAC.md](docs/RBAC.md) for a full explanation of how the RBAC system works and step-by-step instructions for adapting it to your own roles.

## (Completely Optional) Incorporating ML Models into your Project

**This is entirely optional. No part of the project requires a machine learning model, and you are not expected to build one.** The template simply happens to include the plumbing for a hypothetical model, described below, in case your team is curious and has spare time. Skipping this section costs you nothing.

The model shipped in `api/backend/ml_models/model01.py` is a *fake* placeholder — it reads coefficients out of the `model1_params` table and computes a dot product. It is there to show the wiring, not to make real predictions.

If you do want to explore it:

1. Collect and preprocess necessary datasets for your models.
1. Build, train, and test your model in a Jupyter Notebook.
   - You can store your datasets in the `datasets` folder and your notebook in the `ml-src` folder.
1. Once your team is happy with the model's performance, convert your notebook code to a pure Python script.
   - You can include the `training` and `testing` functionality as well as the `prediction` functionality.
   - Develop and test this pure Python script first in the `ml-src` folder.
1. Review the `api/backend/ml_models` module. **Important**: you would never want to hard code the model parameter weights directly in the prediction function — store them in the database, as `model01.py` does.
1. The prediction route for the REST API is in `api/backend/simple/simple_routes.py`. It accepts two URL parameters and passes them to the `predict` function in the `ml_models` module, then packages the result back to Streamlit as JSON.
1. Back in Streamlit, check out `app/src/pages/11_Prediction.py`. Two numeric input fields are created; when the button is pressed, it makes a request to the REST API at `/prediction/{var_01}/{var_02}` and displays the results.
