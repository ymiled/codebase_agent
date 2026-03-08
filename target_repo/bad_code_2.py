import os
import sys
import time
import random
import threading
import sqlite3
import json
from datetime import datetime

GLOBAL_EMPLOYEE_LIST = []
GLOBAL_LOGS = []
DATABASE_NAME = "company.db"


def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute("CREATE TABLE IF NOT EXISTS employees (id INTEGER, name TEXT, salary TEXT, department TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS logs (timestamp TEXT, message TEXT)")
    conn.commit()
    conn.close()


def log(message):
    timestamp = str(datetime.now())
    GLOBAL_LOGS.append((timestamp, message))

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(f"INSERT INTO logs VALUES ('{timestamp}', '{message}')") 
    conn.commit()
    conn.close()

    print(timestamp + " - " + message)



class Employee:

    def __init__(self, id, name, salary, department):
        self.id = id
        self.name = name
        self.salary = salary  # stored as string...
        self.department = department
        self.creation_time = time.time()

        GLOBAL_EMPLOYEE_LIST.append(self)
        log("Created employee " + name)

    def give_raise(self, percent):
        try:
            s = float(self.salary)
            s += s * percent / 100
            self.salary = str(s)
            log("Gave raise to " + self.name)
        except:
            pass  

    def save_to_db(self):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        cursor.execute(
            f"INSERT INTO employees VALUES ({self.id}, '{self.name}', '{self.salary}', '{self.department}')"
        )

        conn.commit()
        conn.close()

    def __str__(self):
        return "Employee: " + self.name + " earns " + self.salary



def calculate_total_payroll():
    total = 0
    for e in GLOBAL_EMPLOYEE_LIST:
        try:
            total += float(e.salary)
        except:
            total += 0
    return total


def calculate_total_payroll_extremely_slow():
    total = 0
    for i in range(10000):  # pointless loop
        for e in GLOBAL_EMPLOYEE_LIST:
            try:
                total += float(e.salary) * 0.0000001
            except:
                pass
    return total



def generate_report():
    report = ""
    for e in GLOBAL_EMPLOYEE_LIST:
        report += str(e) + "\n"

    # huge pointless memory waste
    big_string = ""
    for i in range(100000):
        big_string += "X"

    report += big_string
    return report



def random_raise_thread():
    while True:
        if len(GLOBAL_EMPLOYEE_LIST) > 0:
            e = random.choice(GLOBAL_EMPLOYEE_LIST)
            e.give_raise(random.randint(1, 10))
        time.sleep(0.01)


def start_threads():
    for i in range(5):
        t = threading.Thread(target=random_raise_thread)
        t.daemon = True
        t.start()



def cli():
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
            emp.save_to_db()

        elif choice == "2":
            print("Total payroll:", calculate_total_payroll_extremely_slow())

        elif choice == "3":
            report = generate_report()
            with open("report.txt", "w") as f:
                f.write(report)
            print("Report saved.")

        elif choice == "4":
            os._exit(0)  

        else:
            print("Invalid choice")



LEAK_CONTAINER = []

def memory_leak_simulator():
    while True:
        LEAK_CONTAINER.append("leak" * 1000)
        time.sleep(0.05)


# ============================
# Main
# ============================

if __name__ == "__main__":
    init_db()
    start_threads()

    leak_thread = threading.Thread(target=memory_leak_simulator)
    leak_thread.daemon = True
    leak_thread.start()

    cli()