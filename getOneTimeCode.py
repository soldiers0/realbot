from steampy.guard import generate_one_time_code
import json


def getOneTimeCode(accountName):
    try:
        with open(f'accounts/{accountName}/Steamguard.txt') as file:
            steamGuard = json.load(file)

    except:
        try:
            with open(f'accountStash/{accountName}/Steamguard.txt') as file:
                steamGuard = json.load(file)

        except Exception as e:
            print(f'no such account: {accountName} - {e}')
            return None
    return generate_one_time_code(steamGuard['shared_secret'])


if __name__ == '__main__':
    while True:
        accountName = input()
        print(getOneTimeCode(accountName))

