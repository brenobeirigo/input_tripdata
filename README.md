# Trip data sandbox


## Installing Gurobi on Anaconda

This project implements an ILP model to determine the smallest set of region centers in a network (according to a maximum distance). Follow the steps to run the model:

1. Download and install Gurobi ([link](http://www.gurobi.com/downloads/download-center));
2. Request a free academic license ([link](https://user.gurobi.com/download/licenses/free-academic));
3. Add Gurobi to Anaconda ([link](http://www.gurobi.com/downloads/get-anaconda)).



## Using GIT

Use this project remote:

    https://github.com/brenobeirigo/input_tripdata.git

In the following section, Git tips from the [Git Cheat Sheet](https://www.git-tower.com/blog/) (git-tower).


### Create
Clone an existing repository
    
    git clone <remote>

Create a new local repository
    
    git init
### Update & Publish

List all currently  configured remotes
    
    git remote - v

Download changes and directly merge/integrate into HEAD
    
    git pull <remote> <branch>

#### Publish local changes on a remote
    git push <remote> <branch>

## Loading the python environment

Load the python environment in the file `env_slevels.yaml` to install all modules used in this project.

In the following section, tips on manipulating python environments from the [Anaconda Cheat Sheet](https://docs.conda.io/projects/conda/en/4.6.0/_downloads/52a95608c49671267e40c689e0bc00ca/conda-cheatsheet.pdf).

### Using environments
List all packages and versions installed in active environment

    conda list

Get a list of all my environments, active
environment is shown with *

    conda env list

Create a new environment named py35, install Python 3.5
    
    conda create --name py35 python=3.5 

Create environment from a text file

    conda env create -f environment_name.yaml

Save environment to a text file

    conda env export > environment_name.yaml

## SERVER

The file `server.py` starts a local server to provide easy access to the trip data.


### Adjusting TCP Settings for Heavy Load on Windows

    SOURCE: https://docs.oracle.com/cd/E23095_01/Search.93/ATGSearchAdmin/html/s1207adjustingtcpsettingsforheavyload01.html

    The underlying Search architecture that directs searches across multiple
    physical partitions uses TCP/IP ports and non-blocking NIO SocketChannels
    to connect to the Search engines.
    
    These connections remain open in the TIME_WAIT state until the operating
    system times them out. Consequently, under heavy load conditions,
    the available ports on the machine running the Routing module can be exhausted.

    On Windows platforms, the default timeout is 120 seconds, and the maximum number
    of ports is approximately 4,000, resulting in a maximum rate of 33
    connections per second.
    
    If your index has four partitions, each search requires four ports, 
    which provides a maximum query rate of 8.3 queries per second.

    (maximum ports/timeout period)/number of partitions = maximum query rate
    If this rate is exceeded, you may see failures as the supply of TCP/IP ports is exhausted.
    Symptoms include drops in throughput and errors indicating failed network connections.
    
    You can diagnose this problem by observing the system while it is under load,
    using the netstat utility provided on most operating systems.

    To avoid port exhaustion and support high connection rates,
    reduce the TIME_WAIT value and increase the port range.

    To set TcpTimedWaitDelay (TIME_WAIT):
    - Use the regedit command to access the registry subkey:
        HKEY_LOCAL_MACHINE\
        SYSTEM\
        CurrentControlSet\
        Services\
        TCPIP\
        Parameters
    - Create a new REG_DWORD value named TcpTimedWaitDelay.
    - Set the value to 60.
    - Stop and restart the system.

    To set MaxUserPort (ephemeral port range):
    - Use the regedit command to access the registry subkey:
        HKEY_LOCAL_MACHINE\
        SYSTEM\
        CurrentControlSet\
        Services\
        TCPIP\
        Parameters
    - Create a new REG_DWORD value named MaxUserPort.
    - Set this value to 32768.
    - Stop and restart the system.