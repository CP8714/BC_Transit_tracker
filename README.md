Welcome to the BCTVicTracker

A Bus Tracking and Next Bus tool for BC Transit in Victoria, BC also known as the Victoria Regional Transit System

This website allows users to track a specific BC Transit bus running in Victoria (such as 9542) and get info such as how early/late it is, how busy it is, what route it is running, and the estimated arrival times at every stop on its current trip. Users can also look up the estimated arrival times of the next buses at a specific stop (such as Stop 100032 Douglas St at Fort St). Users can fitler the next arrivals by a specific route and can select if they want variants of that route included (such as including the 6A if the user has fitlered to only view the next arrivals of the 6).

This website downloads publicly available General Transit Feed Specification (GTFS) data from BC Transit including info about a bus' whereabouts, the current trip it is running as well as its current speed. The GTFS data also includes info about trips currently being run including what is the next stop and how late/early it currently is. 

This website is programmed using Plotly Dash, a Python framework for web-based data applications. In addition, this website also relies upon a Github Actions Workflow to periodically download static data from BC Transit (ie data that only changes with seasonal scheduling changes) such as route and schedule information.
