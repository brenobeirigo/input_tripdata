# Trip data sandbox

Generates a complete trip data sandbox to study pickup and delivery problems.


Change the file `config/config_tripdata.json` to choose the region as well as the trip data settings.

The following snippet, for example, chooses the New York street network, and defines the range of request entries that will be pulled from the NYC-TLC trip dataset:

    {
    "region": "Manhattan Island, New York City, New York, USA",
    "url_tripdata": "https://s3.amazonaws.com/nyc-tlc/trip+data/yellow_tripdata_2011-02.csv",
    "start": "2011-2-1",
    "stop": "2011-2-28"
    }

## Mirroring NYC demand to other regions

To copy New York temporal demand distribution (e.g., rush hours, idle times, etc.), the `config_tripdata.json` file have to determine: 
1. The region the demand will be copied to, and
2. The trip data generation settings

The Following snippet shows an example where New York demand is copied to Amsterdam, the Netherlands:

    {
        "region": "Amsterdam, North Holland, Netherlands",
        "data_gen": {
            "source": "D:\\bb\\sq\\data\\manhattan-island-new-york-city-new-york-usa\\tripdata\\tripdata_excerpt_2011-2-1_2011-2-28_ids.csv",
            "funcs": ["random_clone"],
            "max_passenger_count": 4,
            "url_tripdata": "https://s3.amazonaws.com/nyc-tlc/trip+data/yellow_tripdata_2011-02.csv",
            "start": "2011-02-01 00:00:00",
            "stop": "2011-02-02 00:00:00" 
        }
    }

To enter a valid `region`, search it first on [Open Street Map](https://www.openstreetmap.org). For example, the following regions are valid:

* Amsterdam  - `"Amsterdam, North Holland, Netherlands"` (11,372 nodes and 25,759 edges)
* Delft - `"Delft, South Holland, Netherlands"` (2,104 nodes and 4,866 edges)

* Delft - `"Delft University of Technology, Netherlands"` (11,372 nodes and 25,759 edges)

## Installing Gurobi on Anaconda

This project implements an ILP model to determine the smallest set of region centers in a network (according to a maximum distance). Follow the steps to run the model:

1. Download and install Gurobi ([link](http://www.gurobi.com/downloads/download-center));
2. Request a free academic license and activate it ([link](https://user.gurobi.com/download/licenses/free-academic));
3. Add Gurobi to Anaconda ([link](http://www.gurobi.com/downloads/get-anaconda)).

### Common issues

#### License & Gurobi version mismatch
 Occurs when the Python Gurobi package is newer than the Gurobi installation. The license file matches the installation, raising the following issue
 
    Error code 10009: Version number is 8.1, license is for version 7.0
 
 To solve it, install a new Gurobi version or downgrade python version.


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