 #!/bin/bash

 # first arg: either revision or upgrade
 # if first arg is revision, second arg is message for autogenerate

 if [ "$1" = "revision" ]; then
     if [ -z "$2" ]; then
         echo "Error: When using revision, you must provide a message as the second argument"
         exit 1
     fi
     alembic -c elroy/db/sqlite/alembic/alembic.ini revision --autogenerate -m "$2"
     alembic -c elroy/db/postgres/alembic/alembic.ini revision --autogenerate -m "$2"
 elif [ "$1" = "upgrade" ]; then
     alembic -c elroy/db/sqlite/alembic/alembic.ini upgrade head
     alembic -c elroy/db/postgres/alembic/alembic.ini upgrade head
 else
     echo "Error: First argument must be either 'revision' or 'upgrade'"
     echo "Usage: $0 revision \"message\" OR $0 upgrade"
     exit 1
 fi
