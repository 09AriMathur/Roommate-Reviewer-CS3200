# `database-files` Folder

The MySQL server that is running in the db container is set up so that when the container is *created*, any `.sql` files in the `database-files` folder are automatically run. Loosely speaking, the `.sql` files are run in "alphabetical" order. So if your database schema is broken into a few files, it is easiest to rename them with a number at the beginning so they'll be run in the correct order — something like `01_schema.sql`, `02_data.sql` and so on.

If you make changes to any of the files in the `database-files/` folder AFTER the db container is created, you must delete the container **and its volume** before the SQL files will be re-executed. **Note:** stopping and re-starting the db container — or even deleting and re-creating it *without* deleting the volume — will not re-run the files. The MySQL data directory lives in the named `mysql_data` volume, which outlives the container, and MySQL skips initialization whenever it finds that directory already populated.

If you are working with your team repository, do the following:

```bash
docker compose down db -v && docker compose up db -d
```

If you are in your sandbox repo, do the following:

```bash
docker compose -f sandbox.yaml down db -v && docker compose -f sandbox.yaml up db -d
```

The `-v` flag is the part that deletes the `mysql_data` volume, and it is what actually makes the SQL files re-run. Without it, nothing you changed takes effect.

See [../docs/ImportantTips.md](../docs/ImportantTips.md) for more on working with the MySQL container.