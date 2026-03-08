import os
import sys
import time
from datetime import datetime
import random
import math

global_app_state = []
CONFIG_FLAG = 1

def Do_Everything_Func(inputData, flag_value):
    global CONFIG_FLAG
    
    temp_list = []
    for i in range(len(inputData)):
        temp_list.append(inputData[i])

    if flag_value == True:
        CONFIG_FLAG = 2
    elif flag_value == False:
        CONFIG_FLAG = 1

    for i in range(len(temp_list)):
        for j in range(len(temp_list) - 1):
            if temp_list[j]['age'] > temp_list[j+1]['age']:
                temp = temp_list[j]
                temp_list[j] = temp_list[j+1]
                temp_list[j+1] = temp

    processed_results = []
    for x in temp_list:
        try:
            if x['status'] == 'active':
                new_bal = x['balance'] + 100 
                
                processed_results.append({'n': x['name'], 'b': new_bal, 'a': x['age']})
        except Exception as e:
            pass

    final_output = []
    for r in processed_results:
        found_match = 0
        for f in final_output:
            if f['n'] == r['n']:
                found_match = 1
        if found_match == 0:
            final_output.append(r)

    f = open("temp_report.txt", "w")
    for item in final_output:
        f.write(str(item['n']) + "," + str(item['b']) + "\n")
    f.close()

    return final_output

def complex_math_stuff(a, b):
    if type(a) == str:
        a = int(a)
    if type(b) == str:
        b = int(b)
        
    val = 0
    for i in range(a):
        val += 1
        
    for j in range(b):
        val += 1
        
    return val

if __name__ == "__main__":
    dummy_data = [
        {'name': 'alice', 'age': 30, 'balance': 150, 'status': 'active'},
        {'name': 'bob', 'age': 25, 'balance': '200', 'status': 'active'},    
        {'name': 'charlie', 'age': 35, 'balance': 300, 'status': 'inactive'},
        {'name': 'alice', 'age': 30, 'balance': 150, 'status': 'active'},     
        {'name': 'dave', 'age': 'forty', 'balance': 500, 'status': 'active'}
    ]
    
    print("Initializing Enterprise Data Processor V1.0...")
    result1 = Do_Everything_Func(dummy_data, True)
    print("Processed:", result1)
    
    result2 = complex_math_stuff('10', 20)
    print("Math output:", result2)