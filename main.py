from db_handler import init_db, insert_default_torque_table_data
from gui import run_app

def main():
    init_db()
    insert_default_torque_table_data()
    run_app()

if __name__ == "__main__":
    main()
