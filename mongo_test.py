import pymongo

myclient = pymongo.MongoClient("mongodb://192.168.137.7:27017/")

mydb = myclient["mydatabase"]