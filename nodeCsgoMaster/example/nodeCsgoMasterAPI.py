from Naked.toolshed.shell import execute_js, muterun_js, run_js
import multiprocessing
import pathlib
import threading
import multithreading
import json
import sys
import time
import re
import os


class GCRequest:
    def __init__(self, link: str):
        self.link = link
        self.timeIn = time.time()


    def splitInspectMarket(self):
        if 'M' in self.link:
            link = re.split('M|A|D', self.link)
            s = link[1]
            a = link[2]
            d = link[3]
            return '0', a, d, s
        else:
            link = re.split('S|A|D', self.link)
            s = link[1]
            a = link[2]
            d = link[3]
            return s, a, d, '0'


class Connection:
    def __init__(self, username: str, password: str):
        self.path = 'data/nodeCsgoMasterAPITMP/'
        self.isAvailable = False
        self.username = username

        with open(self.path + username + '.txt', 'w') as f:
            f.write('0')
            
        self.thread = multiprocessing.Process(target=run_js, args=('nodeCsgoMaster/example/example.js',))
        self.thread.start()

        with open(f"account.txt", 'w') as f: 
            f.write(username + ';' + password)

        time.sleep(10)

        self.isAvailable = True


    def getItemData(self, request: GCRequest):
        self.isAvailable = False
        s, a, d, m = request.splitInspectMarket()

        with open(f'{self.path}ItemInfo.txt', 'w') as f:
            f.write(s + ';' + a + ';' + d + ';' + m)

        with open(self.username + '.txt', 'w') as f:
            f.write('1')

        while 1:
            with open(f'{self.username}.txt', 'r') as f:
                if f.read() != '1':
                    break

            time.sleep(0.01)

        self.isAvailable = True

        with open(f'answer.json', 'r') as f:
            return json.load(f)


    def close(self):
        self.thread.terminate()
        pathToFile = f'{pathlib.Path(__file__).parent.parent.parent.absolute()}/{self.username}.txt'
        os.remove(pathToFile)


    def reopen(self):
        self.isAvailable = False
        self.close() 

        with open(path + username + '.txt', 'w') as f:
            f.write('0')

        with open(f"{path}/account.txt", 'w') as f:
            f.write(username + ';' + password)

        self.thread = multiprocessing.Process(target=muterun_js, args=('example.js',))
        self.thread.start()

        time.sleep(1)

        self.isAvailable = True





