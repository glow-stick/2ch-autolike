import stem.process
import requests
import time
import sys
import threading

agent = "Mozilla/5.0 (X11; Linux x86_64; rv:73.0) Gecko/20100101 Firefox/73.0"

def get_ip(proxy):
    return requests.get("https://2ip.ru", headers={"User-Agent": agent}, proxies={"https": proxy}).text.split("<big id=\"d_clip_button\">")[1].split("<")[0]

class Multitor:
    def __init__(self, base_port, count):
        self.base_port = base_port
        self.count = count
        self.lock = threading.Lock()
        self.done = 0
        self.processes = []
        threads = []
        for i in range(10):
            thread = threading.Thread(target=self._create_tor_worker)
            threads += [thread]
            thread.start()
        for thread in threads:
            thread.join()
    
    def stop(self):
        for process in self.processes:
            process.terminate()

    def _create_tor_worker(self):
        while True:
            self.lock.acquire()
            port = self.base_port + self.done
            if self.done >= self.count:
                self.lock.release()
                return
            self.done += 1
            self.lock.release()

            try:
                tor = stem.process.launch_tor_with_config(config = {"SocksPort": str(port), "DataDirectory": "./tordata/" + str(port)})
            except Exception as e:
                print(str(port) + ": " + str(e))
                return

            err = False
            try:
                ip = get_ip("socks5://localhost:" + str(port))
            except Exception as e:
                print(e)
                err = True

            self.lock.acquire()
            self.processes += [tor]
            print(str(len(self.processes)) + " / " + str(count) + " " + ("error" if err else ("success (" + ip + ")")))
            self.lock.release()

count = 100
base_port = 39482
multitor = Multitor(base_port, count)
while True:
    try:
        time.sleep(0.1)
    except KeyboardInterrupt:
        print("Stopping")
        multitor.stop()
        print("Stopped")
        sys.exit()
