# Important Tips

## Hot Reloading

In general, any changes you make to the API code base (REST API) or the Streamlit app code should be *hot reloaded* when the files are saved — the changes should be immediately available without restarting containers.

- Don't forget to click the **Always Rerun** button in the browser tab of the Streamlit app for it to reload with changes.
- Sometimes, a bug in the code will cause a container to crash. Fix the bug in the code, then restart the app container in Docker Desktop, or restart all containers with `docker compose restart`. If you are working in your sandbox, add the file flag: `docker compose -f sandbox.yaml restart`.

## The MySQL Container

The MySQL container behaves differently from the app and API containers — be aware of the following:

- When the `db` container is **created** for the first time, MySQL initializes itself by executing the `.sql` files in `./database-files/` in **alphabetical order**. The starter file `ngo_db.sql` holds both schema and data; if you split it up, give the pieces numeric prefixes so they run in the right order — e.g. `01_schema.sql`, `02_data.sql`. Files that are not `.sql` are skipped, so you will see harmless `ignoring /docker-entrypoint-initdb.d/Dockerfile` and `ignoring /docker-entrypoint-initdb.d/README.md` lines in the log.
- This project stores the MySQL data directory in a **named Docker volume** (`mysql_data`), declared in both `docker-compose.yaml` and `sandbox.yaml`. The volume outlives the container.
- **Implication:** stopping, starting, or even deleting and re-creating the `db` container does **not** re-run your `.sql` files. MySQL sees a non-empty data directory in the volume and skips initialization entirely. You must delete the volume to get a fresh database — see below.
- Rows you insert through the Streamlit UI (e.g. via the **Add NGO** page) are written into that volume, so they survive restarts. They are destroyed when you delete the volume. If you want data to always be present after a reset, put it in `database-files/*.sql`.

### When you change a SQL file

You must recreate the container **and delete its volume**. This is what the `-v` flag does.

If you are working with your team repository:

```bash
docker compose down db -v && docker compose up db -d
```

If you are in your sandbox repo:

```bash
docker compose -f sandbox.yaml down db -v && docker compose -f sandbox.yaml up db -d
```

- `docker compose down db -v` stops and removes the MySQL container **and the `mysql_data` volume attached to it**.
- `docker compose up db -d` creates a new container with an empty data directory, which causes MySQL to re-run every `.sql` file in `database-files/`.

> **Leaving off `-v` is the single most common source of "why isn't my schema change showing up?"** Without it the old volume is reused, initialization is skipped, and your edited SQL never runs.

### Reading the logs

The MySQL container's log files are your friend. In Docker Desktop, find the MySQL container and click the **Logs** tab. In your team repo it is named `mysql_db`; in your sandbox, container names are auto-generated, so look for `project-app-personal-sandbox-db-1`. If there are errors in your `.sql` files, they appear here. Use the search 🔍 to look for `Error` to find them quickly. Common culprits: typos, foreign-key references to tables not yet created, and duplicate primary keys.

You can also read them from the terminal:

```bash
# team repo
docker compose logs db

# sandbox
docker compose -f sandbox.yaml logs db
```

> Every bare `docker compose ...` command targets your **team** stack, because `docker-compose.yaml` is the default file. When you are working in your sandbox you must pass `-f sandbox.yaml` every time, or you will silently operate on the wrong containers.
