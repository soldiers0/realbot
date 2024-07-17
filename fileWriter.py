import json
import logging
import copy
import time
from aiofile import async_open

class FileWriter:
	def __init__(self, **kwargs):
		self.backUpDict = {}
		self.BACK_UP_DELAY = 3600 * 12
		self.BACK_UP_AMOUNT = 5

		if 'backUpList' in kwargs:
			backUpList = kwargs['backUpList']
			for file in backUpList:
				self.backUpDict.update({file: [0, 0]})

		if 'BACK_UP_AMOUNT' in kwargs:
			self.BACK_UP_AMOUNT = kwargs['BACK_UP_AMOUNT']

		if 'BACK_UP_DELAY' in kwargs:
			self.BACK_UP_DELAY = kwargs['BACK_UP_DELAY']


	async def writeFile(self, data, filename, isAsync=False):
		extension = filename.split('.')[1]
		attempts = 0

		while True:	
			try:	

				data = json.dumps(data)

				async with async_open(filename, 'w+') as afp:
					await afp.write(data)

				break

			except Exception as e:
				attempts += 1

				if attempts >= 10:
					logging.fatal(f'COULD NOT WRITE DATA IN {filename}: {e}')
					break

				time.sleep(1)


	async def proccesWriting(self, data, path, filename, isAsync=False):
		await self.writeFile(data, f'{path}{filename}')
		extension = filename.split('.')[1]

		if filename in self.backUpDict:
			file = self.backUpDict[filename]

			if time.time() - file[0] < self.BACK_UP_DELAY:
				return

			await self.writeFile(data, f'backups/{filename.split(".")[0]}Backup{file[1]}.{extension}')
			file[0] = time.time()
			file[1] = (file[1] + 1) % self.BACK_UP_AMOUNT

def unJsonCache(itemCache):
	for entry in itemCache:
		itemCache[entry] = set(itemCache[entry])

def getJsonedCache(itemCache):
	itemCache = copy.copy(itemCache)

	for entry in itemCache:
		itemCache[entry] = list(itemCache[entry])

	return itemCache






