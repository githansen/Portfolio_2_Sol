# # ************************** IMPORTS **************************
import argparse
import socket
from saw import *
from utils import *
import time
import random

parser = argparse.ArgumentParser(description="Arguments to invoke server and client", epilog='End of help')
group = parser.add_mutually_exclusive_group()
group.add_argument('-s', '--server', action='store_true')
group.add_argument('-c', '--client', action='store_true')
parser.add_argument('-f', '--file', default='test.jpg')
parser.add_argument('-i', '--ip', default='localhost')
parser.add_argument('-p', '--port', type=int, default=8081)
parser.add_argument('-t', '--test_case', choices=['skipack', 'loss'])
parser.add_argument('-r', '--rel_function', choices=['gbn', 'sw', 'sr'])
parser.add_argument('-w', '--window', type=int, default=5)

# Runs the parser and places the data from the command line
args = parser.parse_args()

def sendClient(sock,seq, ack, flags, win, data):
    data = create_packet(seq,ack,flags,win,data)
    sock.send(data)

def sendAck(sock, client,  ack, data):
    ack_msg = create_packet(0,ack,0,args.window,data)
    sock.sendto(ack_msg, client)


def receiveClient(sock):
    msg = sock.recv(1472)
    return parse_header(msg[:12])

def receiveServer(sock):
    data,client = sock.recvfrom(1472)
    seq, ack, flags, win = parse_header(data[:12])
    return data[12:], client, seq, ack, flags, win 

def swap(list, i, j):
    tempLeft = list[i][0]
    tempRight = list[i][1]

    list[i][0] = list[j][0]
    list[i][1] = list[j][1]

    list[j][0] = tempLeft
    list[j][1] = tempRight

class Server:
    def __init__(self, port, ip, test, rel, file, window):
        self.port = port
        self.ip = ip
        self.test = test
        self.rel = rel
        self.file = file
        self.window = window
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Creates socket
        self.sock.bind((ip,port))
        self.outfile = open(file, "wb") 
        self.data_list = []
        self.sock.setblocking(False)
    
    def stop_and_wait(self):
        expected_seq = 0
        self.sock.settimeout(3)
        b = False
        while True:
            try:
                data, client, seq, ack, flags, win = receiveServer(self.sock)
            except:
                break
            if seq == expected_seq:
                self.outfile.write(data)
                expected_seq += 1
            if b:
                sendAck(self.sock,client,seq, b"")
                print(seq)
            else:
                b = True


    def go_back_n(self):
        expected_seq = 0
        self.sock.settimeout(3)
        b = False
        while True:
            try:
                data, client, seq, ack, flags, win = receiveServer(self.sock)
                print(seq)
                if seq <= expected_seq:
                    if seq == expected_seq:
                        if b:
                            sendAck(self.sock,client,expected_seq,b"")
                            expected_seq += 1
                            self.outfile.write(data)
                        else:
                            b = True
                    else:
                        sendAck(self.sock, client, seq, b"")

                    
            except:
                break

    def gbn_sr(self):
        expected_seq = 0
        self.sock.settimeout(3)
        b = False
        outlist = []
        while True:
            try:
                data, client, seq, ack, flags, win = receiveServer(self.sock)
                print(seq)
                if seq >= expected_seq:
                    if [seq, data] not in outlist:
                        outlist.append([seq, data])
                    if seq == expected_seq:
                        if b:
                            sendAck(self.sock,client,expected_seq,b"")
                            expected_seq += 1
                            
                        else:
                            b = True
                    else:
                        sendAck(self.sock, client, seq, b"")     
                else:
                    sendAck(self.sock, client, seq, b"")
            except:
                break

        for i in range(len(outlist)):
            for j in range(i,len(outlist), 1):
                if outlist[i][0] > outlist[j][0]:
                    print("SWAPPING")
                    swap(outlist, i, j)

        for i in outlist:
            self.outfile.write(i[1])
        for i in outlist:
            print(i[0])
        self.outfile.close()

class Client:
    def __init__(self, port, ip, test, rel, file, window):
        self.port = port
        self.ip = ip
        self.test = test
        self.rel = rel
        self.file = file
        self.window = window
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Creates socket
        self.sock.connect((ip,port)) # Connects to server
        
        send_file = open(file, "rb")
        self.data_list = []
        while True:
            data = send_file.read(1460)
            self.data_list.append(data)
            if not data:
                break

    

    def stop_and_wait(self):
        next_seq = 0
        print("KLIENT STARTER")
        self.sock.settimeout(0.5)
        while next_seq < len(self.data_list):
            #print(f"SENDER {next_seq}")
            sendClient(self.sock, next_seq, 0,0,self.window, self.data_list[next_seq])
            try:
                seq, ack, flags, win = receiveClient(self.sock)
                if ack == next_seq:
                    next_seq += 1
                else:
                    print(f"Received ack for {ack}, expected ack for {next_seq}. Retransmitting")
            except:
                print(f"Didn't receive ack in time, retransmitting")
                continue
            

    def go_back_n(self):
        base = 0
        next_seq = 0
        window_size = self.window
        self.sock.settimeout(0.5)
        b = False
        seqList = []
        for i in range(len(self.data_list)):
            seqList.append(i)
        print(seqList)
        while base < len(self.data_list):
            print(f"Current window: {seqList[base:base+window_size]}")
            print(f"Sending: {seqList[next_seq:base+window_size]}")
            while next_seq < len(self.data_list) and next_seq < base+window_size:
                if b:
                    sendClient(self.sock, next_seq, 0,0,self.window, self.data_list[next_seq-1])
                    #print(f"Sending {next_seq}")
                    next_seq += 1
                else:
                    b = True               
            try:
                seq, ack, flags, win = receiveClient(self.sock)
                print(f"Received ack NO {ack}")
                print()
                if ack == base:
                    base += 1
                else:
                    next_seq = base
            except:
                next_seq = base

    def gbn_sr(self):
        self.sock.settimeout(0.5)
        base = 0
        next_seq = 0
        window_size = self.window
        Unacked_packets = []
        last_acked = -1
      
        b = False
        while (base < len(self.data_list) or len(Unacked_packets)>0) or base == 0:
            retransmit = False
            print(Unacked_packets)
            for i in Unacked_packets:
                if i < last_acked:
                    retransmit = True
                    #print(f"Sending {i}")
                    sendClient(self.sock, i,0,0,window_size, self.data_list[i])

            if not retransmit:
                while len(Unacked_packets) < window_size and next_seq < len(self.data_list):
                    #print(f"Sending {next_seq}")
                    if b:
                        sendClient(self.sock, next_seq, 0,0,window_size, self.data_list[next_seq])
                    else:
                        b = True
                    if next_seq not in Unacked_packets:
                        Unacked_packets.append(next_seq)
                    next_seq += 1
                
            print(base)
            try:
                seq, ack, flags, win = receiveClient(self.sock)
                last_acked = ack
                print(f"Received ACK NO {ack}")
                if ack in Unacked_packets:
                    Unacked_packets.remove(ack)
                    base +=1
                else: 
                    next_seq = base
            except:
                #print("ERROR")
                next_seq = base




if __name__ == '__main__':
    port, ip, test, rel, file, window = parse_attributes(args)

    if args.server:
        sock = Server(port, ip, test, rel, file, window)

    if args.client:
        sock = Client(port, ip, test, rel, file,window)


    if args.rel_function == "sw":
        sock.stop_and_wait()
    elif args.rel_function == "gbn":
        sock.go_back_n()
    else: 
        sock.gbn_sr()