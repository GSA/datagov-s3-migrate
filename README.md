# s3 migration

Copies objects from one bucket in one account to another bucket in another
account.

## Usage

1. Download and unzip the gist
1. Setup python virtualenv
1. Populate the environment
1. Run the script

### Download gist

Download and unzip this gist on dashboardweb1p.

### Setup python virtualenv

Run these on on dashboardweb1p.

You may need to install python3-venv with apt-get.

    $ python3 -m venv venv
    $ source venv/bin/activate
    $ pip install -r requirements.txt

### Populate the environment

env.sample contains the structure

    $ env_file=$(mktemp)
    $ vi $env_file

SRC credentials are the FCS environment. Bucket name is found in /var/www/dashboard/current/.env.

DEST variables come from the cloud.gov service-key, these are run on your local
development environment.

    $ cf target -s $space
    $ cf service-key dashboard-s3 fcs-migration

### Run the script

Run these steps on dashboardweb1p in a tmux environment.

    $ source $env_file
    $ source venv/bin/activate
    $ time python migrate.py --use-ec2


## requirements.txt

With Pipfile/pipenv, the requirements.txt isn't really necessary but simplifies
deployment when pipenv is not available. Update the requirements.txt from
pipenv:

    $ pipenv lock -r > requirements.txt


## Cloud.gov

You can run this in cloud.gov...

    $ cf create-service s3 basic-public dashboard-s3-public

Push the application.

    $ cf push -f manifest.yml s3-migrator

Run the script.

    $ cf run-task s3-migrator --command "python migrate.py --prefix datagov/dashboard/ --src-service-name dashboard-s3 --dest-service-name dashboard-s3-public" --name dashboard-s3-public --wait
