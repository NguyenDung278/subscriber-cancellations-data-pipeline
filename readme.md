Subscriber Cancellations Data Pipeline project
This repository contains example code to complete the Codecademy Subscriber Cancellations Data Pipeline Project.

Project Description
A semi-automated bash+python pipeline to regularly transform a messy SQLite database into a clean source of truth for an analytics team.

The pipeline

performs unit tests to confirm data validity
writes human-readable errors to an error log
automatically checks and updates changelogs
updates a production database with new clean data
Please see writeup/article.md for an overview of the development process and writeup/data_eng_cp_writeup.ipynb for an exploratory Jupyter notebook.

Instructions
This repository is set up as if the scripts have never been run. To run,

Run script.sh and follow the prompts
If prompted, script.sh will run dev/cleanse_data.py, which runs unit tests and data cleaning functions on dev/cademycode.db
If cleanse_data.py runs into any errors during unit testing, it will raise an exception, log the issue, and terminate
Otherwise, cleanse_data.py will update the clean database and CSV with any new records
After a successful update, the number of new records and other update data will be written to dev/changelog.md
script.sh will check the changelog to see if there are updates
If so, script.sh will request permission to overwrite the production database
If the user grants permission, script.sh will copy the updated database to prod