import sqlite3
import pandas as pd
import ast
import numpy as np
from sqlalchemy import create_engine
import logging

pd.options.mode.chained_assignment = None

logging.basicConfig(filename="./dev/cleanse_db.log",
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    filemode='w',
                    level=logging.DEBUG,
                    force=True)
logger = logging.getLogger(__name__)

def cleanse_student_table(df):
    now = pd.to_datetime('now')
    df['age'] = (now - pd.to_datetime(df['dob'])).astype('<m8[Y]')
    df['age_group'] = np.int64((df['age']/10))*10

    df['contact_info'] = df["contact_info"].apply(lambda x: ast.literal_eval(x))
    explode_contact = pd.json_normalize(df['contact_info'])
    df = pd.concat([df.drop('contact_info', axis=1).reset_index(drop=True), explode_contact], axis=1)

    split_address = df.mailing_address.str.split(',', expand=True)
    split_address.columns = ['street', 'city', 'state', 'zip_code']
    df = pd.concat([df.drop('mailing_address', axis=1), split_address], axis=1)

    df['job_id'] = df['job_id'].astype(float)
    df['current_career_path_id'] = df['current_career_path_id'].astype(float)
    df['num_course_taken'] = df['num_course_taken'].astype(float)
    df['time_spent_hrs'] = df['time_spent_hrs'].astype(float)

    missing_data = pd.DataFrame()
    missing_course_taken = df[df[['num_course_taken']].isnull().any(axis=1)]
    missing_data = pd.concat([missing_data, missing_course_taken])
    df = df.dropna(subset=['num_course_taken'])

    missing_job_id = df[df[['job_id']].isnull().any(axis=1)]
    missing_data = pd.concat([missing_data, missing_job_id])
    df = df.dropna(subset=['job_id'])

    df['current_career_path_id'] = np.where(df['current_career_path_id'].isnull(), 0, df['current_career_path_id'])
    df['time_spent_hrs'] = np.where(df['time_spent_hrs'].isnull(), 0, df['time_spent_hrs'])

    return(df, missing_data)


def cleanse_career_path(df):
    not_applicable = {'career_path_id': 0,
                      'career_path_name': 'not applicable',
                      'hours_to_complete': 0}
    df.loc[len(df)] = not_applicable
    return(df.drop_duplicates())


def cleanse_student_jobs(df):
    return(df.drop_duplicates())


def test_nulls(df):
    df_missing = df[df.isnull().any(axis=1)]
    cnt_missing =len(df_missing)
    try:
        assert cnt_missing == 0, "There are " + str(cnt_missing) + " nulls in the table"
    except AssertionError as ae:
        logger.exception(ae)
        raise ae
    else:
        print('No null rows found.')


def test_schema(local_df, db_df):
    errors = 0
    for col in db_df:
        try:
            if local_df[col].dtypes != db_df[col].dtypes:
                errors+=1
        except NameError as ne:
            logger.exception(ne)
            raise ne

    if errors > 0:
        assert_err_msg = str(errors) + " column(s) dtypes aren't the same"
        logger.exception(assert_err_msg)
    assert errors == 0, assert_err_msg

def test_num_cols(local_df, db_df):
    try:
        assert len(local_df.columns) == len(db_df.columns)
    except AssertionError as ae:
        logger.exception(ae)
        raise ae
    else:
        print('Number of columns are the same.')

def test_for_path_id(students, career_paths):
    student_table = students.current_career_path_id.unique()
    is_subset = np.isin(student_table, career_paths.career_path_id.unique())
    missing_id = student_table[~is_subset]
    try:
        assert len(missing_id) == 0, "Missing career_path_id(s): " + str(list(missing_id)) + " in `career_paths` table"
    except AssertionError as ae:
        logger.exception(ae)
        raise ae
    else:
        print('All career_path_ids are present.')        

def test_for_job_id(students, student_jobs):
    student_table = students.job_id.unique()
    is_subset = np.isin(student_table, student_jobs.job_id.unique())
    missing_id = student_table[~is_subset]
    try:
        assert len(missing_id) == 0, "Missing job_id(s): " + str(list(missing_id)) + " in `student_jobs` table"
    except AssertionError as ae:
        logger.exception(ae)
        raise ae
    else:
        print('All job_ids are present.')

def main():
    logger.info("Start Log")

    with open('./changelog.md') as f:
        lines = f.readlines()
    if len(lines)==0:
        next_ver = 0
    else:
        next_ver = int(lines[0].split('.')[2][0])+1
    con = sqlite3.connect('./ cademycode.db')
    students = pd.read_sql_query("SELECT * FROM cademycode_students", con)
    career_paths = pd.read_sql_query("SELECT * FROM cademycode_courses", con)
    student_jobs = pd.read_sql_query("SELECT * FROM cademycode_student_jobs", con)
    con.close()
    try:
        con = sqlite3.connect('./cademycode_cleansed.db')
        clean_db = pd.read_sql_query("SELECT * FROM cademycode_aggregated", con)
        missing_db = pd.read_sql_query("SELECT * FROM incomplete_data", con)
        con.close()

        # filter for students that don't exist in the cleansed database
        new_students = students[~np.isin(students.uuid.unique(), clean_db.uuid.unique())]
    except:
        new_students = students
        clean_db = [] 
    clean_new_students, missing_data = cleanse_student_table(new_students)
    try:
        new_missing_data = missing_data[~np.isin(missing_data.uuid.unique(), missing_db.uuid.unique())]
    except:
        new_missing_data = missing_data

    # upsert new incomplete data if there are any
    if len(new_missing_data) > 0:
        sqlite_connection = sqlite3.connect('./dev/cademycode_cleansed.db')
        missing_data.to_sql('incomplete_data', sqlite_connection, if_exists='append', index=False)
        sqlite_connection.close()
    if len(clean_new_students) > 0:
        clean_career_paths = cleanse_career_path(career_paths)
        clean_student_jobs = cleanse_student_jobs(student_jobs)
        test_for_job_id(clean_new_students, clean_student_jobs)
        test_for_path_id(clean_new_students, clean_career_paths)

        clean_new_students['job_id'] = clean_new_students['job_id'].astype(int)
        clean_new_students['current_career_path_id'] = clean_new_students['current_career_path_id'].astype(int)

        df_clean = clean_new_students.merge(
            clean_career_paths, 
            left_on='current_career_path_id', 
            right_on='career_path_id', 
            how='left')
        df_clean = df_clean.merge(clean_student_jobs, on='job_id', how='left')
        if len(clean_db) > 0:
            test_num_cols(df_clean, clean_db)
            test_schema(df_clean, clean_db)
        test_nulls(df_clean)

        con = create_engine('sqlite:///./cademycode_cleansed.db', echo=True)
        sqlite_connection = con.connect()
        df_clean.to_sql('cademycode_aggregated', sqlite_connection, if_exists='append', index=False)
        clean_db = pd.read_sql_query("SELECT * FROM cademycode_aggregated", con)
        sqlite_connection.close()
        clean_db.to_csv('./cademycode_cleansed.csv')

        new_lines = [
            '## 0.0.' + str(next_ver) + '\n' +
            '### Added\n' +
            '- ' + str(len(df_clean)) + ' more data to database of raw data\n' +
            '- ' + str(len(new_missing_data)) + ' new missing data to incomplete_data table\n' +
            '\n'
        ]

        w_lines = ''.join(new_lines + lines)

        # update the changelog
        with open('./changelog.md', 'w') as f:
            for line in w_lines:
                f.write(line)
    else:
        print("No new data")
        logger.info("No new data")
    logger.info("End Log")
if __name__ == "__main__":
    main()