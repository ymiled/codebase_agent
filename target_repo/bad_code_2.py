import sys
import logging
from typing import List, Tuple
import sqlite3
import json
from datetime import datetime
import threading
import random
import time

# Encapsulate global state within a class
class GameState:
    def __init__(self):
        self.state = {}
        self.employees = []
        self.logs = []

    def update_state(self, key: str, value: str):
        self.state[key] = value

    def add_employee(self, employee):
        self.employees.append(employee)

    def add_log(self, log):
        self.logs.append(log)

# Use parameterized queries to prevent SQL injection
def execute_query(query: str, params: Tuple[str, str]) -> None:
    try:
        # Use a parameterized query to prevent SQL injection
        conn = sqlite3.connect('company.db')
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        conn.close()
    except OSError as e:
        logging.error(f"Error executing query: {e}")

# Use specific exception handling
def handle_exception(exception: Exception) -> None:
    if isinstance(exception, OSError):
        logging.error(f"OS error: {exception}")
    elif isinstance(exception, TypeError):
        logging.error(f"Type error: {exception}")
    else:
        logging.error(f"Unknown error: {exception}")

# Use structured logging for file operations
def write_to_file(file_path: str, content: str) -> None:
    try:
        logging.info(f"Writing to file: {file_path}")
        with open(file_path, 'w') as f:
            f.write(content)
        logging.info(f"File written successfully: {file_path}")
    except OSError as e:
        logging.error(f"Error writing to file: {e}")

# Use sys.exit instead of os._exit
def exit_program() -> None:
    sys.exit(0)

class Employee:
    def __init__(self, id: str, name: str, salary: str, department: str):
        self.id = id
        self.name = name
        self.salary = salary
        self.department = department
        self.creation_time = datetime.now()

    def give_raise(self, percent: float) -> None:
        try:
            s = float(self.salary)
            s += s * percent / 100
            self.salary = str(s)
            logging.info(f"Gave raise to {self.name}")
        except (ValueError, TypeError) as e:
            handle_exception(e)

    def save_to_db(self) -> None:
        try:
            execute_query("INSERT INTO employees VALUES (?, ?, ?, ?)", (self.id, self.name, self.salary, self.department))
        except OSError as e:
            handle_exception(e)

    def __str__(self) -> str:
        return f"Employee: {self.name} earns {self.salary}"


def calculate_total_payroll(game_state: GameState) -> float:
    total = 0
    for e in game_state.employees:
        try:
            total += float(e.salary)
        except ValueError:
            pass
    return total


def calculate_total_payroll_extremely_slow(game_state: GameState) -> float:
    total = 0
    for i in range(10000):
        for e in game_state.employees:
            try:
                total += float(e.salary) * 0.0000001
            except ValueError:
                pass
    return total


def generate_report(game_state: GameState) -> str:
    report = ""
    for e in game_state.employees:
        report += str(e) + "\n"
    return report


def random_raise_thread(game_state: GameState) -> None:
    while True:
        if game_state.employees:
            e = random.choice(game_state.employees)
            e.give_raise(random.uniform(1, 10))
        time.sleep(0.01)


def start_threads(game_state: GameState) -> None:
    for i in range(5):
        t = threading.Thread(target=random_raise_thread, args=(game_state,))
        t.daemon = True
        t.start()


def cli(game_state: GameState) -> None:
    while True:
        print("1. Add employee")
        print("2. Show total payroll")
        print("3. Generate report")
        print("4. Exit")
        choice = input("Choice: ")
        if choice == "1":
            id = input("ID: ")
            name = input("Name: ")
            salary = input("Salary: ")
            department = input("Department: ")
            emp = Employee(id, name, salary, department)
            game_state.add_employee(emp)
            emp.save_to_db()
        elif choice == "2":
            print("Total payroll: ", calculate_total_payroll_extremely_slow(game_state))
        elif choice == "3":
            report = generate_report(game_state)
            write_to_file("report.txt", report)
            print("Report saved.")
        elif choice == "4":
            exit_program()
        else:
            print("Invalid choice")


def main() -> None:
    game_state = GameState()
    init_db = sqlite3.connect('company.db')
    cursor = init_db.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS employees (id TEXT, name TEXT, salary TEXT, department TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS logs (timestamp TEXT, message TEXT)")
    init_db.commit()
    init_db.close()
    start_threads(game_state)
    cli(game_state)

if __name__ == "__main__":
    main()