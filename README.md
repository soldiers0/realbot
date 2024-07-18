# Overview
This is a person project that was developed by me during years 2020-2023. The idea is to parse the csgo/cs2 steam community market for items with rare patterns and/or float values to then resell for profit. 
The project ceased to be viable, thus I am open sourcing it, since some parts may be interesting to other people.

# project structure

## csmoney

Csmoney folder is dedicated to all csmoney-related things. An unstable or maybe even totally outdated [inventory handler](csmoney/csmoneyInventoryHandler.py), a [parser](csmoney/csmoneyParser.py), and the most interesing 
[overpay analyzer](csmoney/csmOverpayAnalyzers.py) module. This module finds the best curve to approximate the float-to-overpay relation on csmoney. It is then used in the main parser, to choose the potentially most profitable items.

## steam

Nothing particularly interesting here, mostly just a wrapper for the steampy library. Some things like maintaining a logged-in session were re-implemented to be more stable. 

## request handler 

This file implements am icp request queue with rotating proxies. It keeps track of how the proxies are performing on different hosts and allows for their efficient use by multiple processes.

# Issues with the project

For anyone who has found this project, and is looking to implement something similar, or use this code, here are the problems that eventually led me to stop working on this project

## csgofloat

Csgofloat used to have an open api for fetching float and pattern values for different items. The self-hosted solution was adapted by this code, but without the economy-of-scale advantage of caching the whole market, the speed was not satisfactory.
The interesting fact is that doppler phases can actually be distinguished by the picture displayed with the listing, which is probably alread exploited by hundreds if not thousands of other bots.
[Here](csgofloat.py?plain=1#L43) is how it works, not all that complicated.

## steam returning cached pages

This is the main problem. Since about 2022 steam started more aggressively returning cached versions of market pages, thus making the race the be the first to find an item very inconsistent. There has to be a work-around this problem, in my own testing 
requesting a page from a logged-in account helps. Diversifying the proxy-geography might also help.

If these problems were to be solved, this kind of system couldan turn good consistent profit, even without going for blue-chips item like dopplers or case-hardened knives. 
