FROM mysql:9

# Bake the seed/schema SQL files into the image so they ship with the
# container in any environment (Coolify, Hetzner, plain Docker, etc.)
# without depending on bind mounts. MySQL runs these in alphabetical order
# on first container start when /var/lib/mysql is empty.
COPY *.sql /docker-entrypoint-initdb.d/
