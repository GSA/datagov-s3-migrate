# s3 migration

Copies objects from one bucket in one account to another bucket in another
account.

## Usage

1. Clone this repo
1. Setup python virtualenv
1. Populate the environment
1. Run the script

### Clone this repo

Clone this repo to wordpress1p.

### Setup python virtualenv

Run these on on wordpress1p.

You may need to install python3-venv with apt-get.

    $ python3 -m venv venv
    $ source venv/bin/activate
    $ pip install -r requirements.txt

### Populate the environment

env.sample contains the environment template.

    $ cp env.sample .env
    $ vi .env

SRC credentials are the FCS environment. Bucket name is found in /var/www/datagov/current/.env.

DEST variables come from the cloud.gov service-key, these are run on your local
development environment.

    $ cf target -s $space
    $ cf service-key fcs-lifeboat fcs-migration

### Run the script

Run these steps on wordpress1p in a tmux environment.

    $ source .env
    $ source venv/bin/activate
    $ time python migrate.py --use-ec2


## requirements.txt

With Pipfile/pipenv, the requirements.txt isn't really necessary but simplifies
deployment when pipenv is not available. Update the requirements.txt from
pipenv:

    $ pipenv lock -r > requirements.txt


## Cloud.gov

You can run this in cloud.gov. Add the s3 service to the manifest.yml.

Push the application.

    $ cf push -f manifest.yml s3-migrator

Run the migrate task.

    $ cf run-task s3-migrator --command "python migrate.py --prefix datagov/dashboard/ --src-service-name fcs-lifeboat --dest-service-name dashboard-s3" --name dashboard-s3 --wait
