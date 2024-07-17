var Steam = require("steam"),
    process = require("process"),
    util = require("util"),
    fs = require("fs"),
    csgo = require("../"),
    bot = new Steam.SteamClient(),
    steamUser = new Steam.SteamUser(bot),
    steamGC = new Steam.SteamGameCoordinator(bot, 730),
    CSGOCli = new csgo.CSGOClient(steamUser, steamGC, true),
    readlineSync = require("readline-sync"),
    crypto = require("crypto");
    dataDirPath = __dirname + '/../../data/nodeCsgoMasterAPITMP/'

Steam.servers = require('./servers.json')

function MakeSha(bytes) {
    var hash = crypto.createHash('sha1');
    hash.update(bytes);
    return hash.digest();
}

function Print(itemdata, accountName) {
    console.log(itemdata);
    fs.writeFileSync('Answer' + name + '.json', JSON.stringify(itemdata, null, 2));
}

function Sas(a, b, c, d) {
    CSGOCli.itemDataRequest(a, b, c, d);
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function onSteamLogOn(response){
    CSGOCli.launch();
    CSGOCli.on("ready", function() {
        util.log("node-csgo ready.");

        CSGOCli.matchmakingStatsRequest();
        CSGOCli.on("matchmakingStatsData", async function(matchmakingStatsResponse) {
            // steam://rungame/730/76561202255233023/+csgo_econ_action_preview%20S76561198084749846A6768147729D12557175561287951743
            CSGOCli.on("itemData", Print);
            console.log("Connection create");
            while (1) {
                await sleep(1);
                if (fs.readFileSync(dataDirPath + name + '.txt').toString() == '1') {
                    var inputData = fs.readFileSync(dataDirPath + 'ItemInfo.txt').toString().split(';');
                    Sas(inputData[0], inputData[1], inputData[2], inputData[3]);
                    fs.writeFileSync(dataDirPath + name + '.txt', "0");
                }
            }

        });
    });

    CSGOCli.on("unready", function onUnready(){
        util.log("node-csgo unready.");
    });

    CSGOCli.on("unhandled", function(kMsg) {
        util.log("UNHANDLED MESSAGE " + kMsg);
    });

}

function onSteamSentry(sentry) {
    util.log("Received sentry.");
    require('fs').writeFileSync('sentry', sentry);
}

function onSteamServers(servers) {
    util.log("Received servers.");
    fs.writeFileSync('servers.json', JSON.stringify(servers, null, 2));
}


var data = fs.readFileSync(dataDirPath + 'account.txt');
var name = data.toString().split(';')[0];

var logOnDetails = {
    "account_name": data.toString().split(';')[0],
    "password": data.toString().split(';')[1],
};

console.log(logOnDetails);

var sentry = fs.readFileSync(__dirname + '/sentry');
if (sentry.length) {
    logOnDetails.sha_sentryfile = MakeSha(sentry);
}
bot.connect();
steamUser.on('updateMachineAuth', function(response, callback){
    fs.writeFileSync('sentry', response.bytes);
    callback({ sha_file: MakeSha(response.bytes) });
});
bot.on("logOnResponse", onSteamLogOn)
    .on('sentry', onSteamSentry)
    .on('servers', onSteamServers)
    .on('connected', function(){
        steamUser.logOn(logOnDetails);
    });