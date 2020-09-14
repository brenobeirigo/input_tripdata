# Creating static instances

Execute the file `create_instances.py` to pull random trips from the trip data file.
A trip data file (e.g., `tripdata_excerpt_2011-2-1_2011-2-28_ids.csv`) is expected to contain the following:

| pickup_datetime     | passenger_count | pk_id | dp_id | pickup_latitude | pickup_longitude | dropoff_latitude | dropoff_longitude |
|---------------------|-----------------|-------|-------|-----------------|------------------|------------------|-------------------|
| 2011-02-01 00:00:00 | 1               | 2527  | 669   | 40.769223       | -73.982005       | 40.801843        | -73.949197        |
| 2011-02-01 00:00:00 | 1               | 1266  | 3752  | 40.772162       | -73.952847       | 40.780745        | -73.946672        |
| 2011-02-01 00:00:00 | 1               | 4250  | 3347  | 40.760737       | -73.975547       | 40.733373        | -74.003043        |
| 2011-02-01 00:00:00 | 1               | 1137  | 1114  | 40.808022       | -73.964057       | 40.73749         | -74.008177        |
| 2011-02-01 00:00:00 | 2               | 1503  | 2335  | 40.738107       | -73.983683       | 40.767477        | -73.953305        |




The script will create files such as `manhattan-island-new-york-city-new-york-usa__005__AA__A-68_B-16_C-16__001__maxpcount_01.csv` that contain that as follows:

| pickup_datetime     | passenger_count | pk_id | dp_id | pickup_latitude | pickup_longitude | dropoff_latitude | dropoff_longitude | service_class |
|---------------------|-----------------|-------|-------|-----------------|------------------|------------------|-------------------|---------------|
| 2011-02-01 00:00:08 | 1               | 769   | 3176  | 40.751015       | -73.991062       | 40.763849        | -73.977217        | A             |
| 2011-02-01 00:00:17 | 1               | 3005  | 2137  | 40.742575       | -73.982804       | 40.763214        | -73.992609        | B             |
| 2011-02-01 00:00:21 | 1               | 3290  | 3377  | 40.763069       | -73.96741        | 40.766615        | -73.951704        | A             |
| 2011-02-01 00:00:24 | 1               | 2593  | 2064  | 40.799431       | -73.968441       | 40.750246        | -73.994898        | A             |
| 2011-02-01 00:00:28 | 1               | 3095  | 2400  | 40.733309       | -73.999745       | 40.739309        | -73.990088        | A             |


# Running static istances

Execute `run_darp_sq.py`. The file will create a set of vehicles at the closest region centers of each request (function `get_list_of_vehicles_in_region_centers`).
You can choose creating a heterogeneous by setting  (`fixed_capacity = False`).
The aggregate results will be saved in a `results.csv` file as follows:

| test       | instance                                                                                            | passenger_count | id_instance | demand_size | group_id | max_vehicle_capacity | fleet_size | total_capacity | user_base | objective_function          | run_time    | fleet_capacity_obj_val | total_delay_obj_val | fleet_capacity_obj_mip_gap | total_delay_obj_mip_gap | capacity_01 | capacity_02 | capacity_03 | capacity_04 | pk_delay_mean_A | pk_delay_mean_B | pk_delay_mean_C | pk_delay_sum_A | pk_delay_sum_B | pk_delay_sum_C | ride_delay_mean_A | ride_delay_mean_B | ride_delay_mean_C | ride_delay_sum_A | ride_delay_sum_B | ride_delay_sum_C | tier_1 | tier_1_A | tier_1_B | tier_1_C | tier_1_pk_delay_sum | tier_1_pk_delay_sum_A | tier_1_pk_delay_sum_B | tier_1_pk_delay_sum_C | tier_1_ride_delay_sum | tier_1_ride_delay_sum_A | tier_1_ride_delay_sum_B | tier_1_ride_delay_sum_C | tier_2 | tier_2_A | tier_2_B | tier_2_C | tier_2_pk_delay_sum | tier_2_pk_delay_sum_A | tier_2_pk_delay_sum_B | tier_2_pk_delay_sum_C | tier_2_ride_delay_sum | tier_2_ride_delay_sum_A | tier_2_ride_delay_sum_B | tier_2_ride_delay_sum_C | total | total_A | total_B | total_C | total_delay | total_pk_delay | total_pk_delay_A | total_pk_delay_B | total_pk_delay_C | total_ride_delay | total_ride_delay_A | total_ride_delay_B | total_ride_delay_C |
|------------|-----------------------------------------------------------------------------------------------------|-----------------|-------------|-------------|----------|----------------------|------------|----------------|-----------|-----------------------------|-------------|------------------------|---------------------|----------------------------|-------------------------|-------------|-------------|-------------|-------------|-----------------|-----------------|-----------------|----------------|----------------|----------------|-------------------|-------------------|-------------------|------------------|------------------|------------------|--------|----------|----------|----------|---------------------|-----------------------|-----------------------|-----------------------|-----------------------|-------------------------|-------------------------|-------------------------|--------|----------|----------|----------|---------------------|-----------------------|-----------------------|-----------------------|-----------------------|-------------------------|-------------------------|-------------------------|-------|---------|---------|---------|-------------|----------------|------------------|------------------|------------------|------------------|--------------------|--------------------|--------------------|
| slevels    | slevels__manhattan-island-new-york-city-new-york-usa__015__AA__A-68_B-16_C-16__001__maxpcount_01    | maxpcount_01    | 1           | 15          | 015_AA   | 4                    | 15         | 60             | AA        | fleet_capacity__total_delay | 18000.70955 | 32                     | 18847               | 0.0001                     | 0.0001                  | 0           | 0           | 0           | 8           | 100.6666667     | 154             | 487.7142857     | 604            | 308            | 3414           | 0                 | 287               | 74.57142857       | 0                | 574              | 522              | 15     | 6        | 2        | 7        | 4326                | 604                   | 308                   | 3414                  | 1096                  | 0                       | 574                     | 522                     | 0      | 0        | 0        | 0        | 0                   | 0                     | 0                     | 0                     | 0                     | 0                       | 0                       | 0                       | 15    | 6       | 2       | 7       | 5422        | 4326           | 604              | 308              | 3414             | 1096             | 0                  | 574                | 522                |
| baseline_1 | baseline_1__manhattan-island-new-york-city-new-york-usa__015__AA__A-68_B-16_C-16__001__maxpcount_01 | maxpcount_01    | 1           | 15          | 015_AA   | 4                    | 15         | 60             | AA        | fleet_capacity__total_delay | 2586.244362 | 32                     | 4181                | 0.0001                     | 0.0001                  | 0           | 0           | 0           | 8           | 100.6666667     | 154             | 466             | 604            | 308            | 3262           | 0                 | 0                 | 1                 | 0                | 0                | 7                | 15     | 6        | 2        | 7        | 4174                | 604                   | 308                   | 3262                  | 7                     | 0                       | 0                       | 7                       | 0      | 0        | 0        | 0        | 0                   | 0                     | 0                     | 0                     | 0                     | 0                       | 0                       | 0                       | 15    | 6       | 2       | 7       | 4181        | 4174           | 604              | 308              | 3262             | 7                | 0                  | 0                  | 7                  |
| baseline_2 | baseline_2__manhattan-island-new-york-city-new-york-usa__015__AA__A-68_B-16_C-16__001__maxpcount_01 | maxpcount_01    | 1           | 15          | 015_AA   | 4                    | 15         | 60             | AA        | fleet_capacity__total_delay | 18001.17784 | 24                     | 22778               | 0.0001                     | 0.0001                  | 0           | 0           | 0           | 6           | 183.6666667     | 600             | 1125.142857     | 1102           | 1200           | 7876           | 0                 | 150               | 42.85714286       | 0                | 300              | 300              | 15     | 6        | 2        | 7        | 10178               | 1102                  | 1200                  | 7876                  | 600                   | 0                       | 300                     | 300                     | 0      | 0        | 0        | 0        | 0                   | 0                     | 0                     | 0                     | 0                     | 0                       | 0                       | 0                       | 15    | 6       | 2       | 7       | 10778       | 10178          | 1102             | 1200             | 7876             | 600              | 0                  | 300                | 300                |


Logs are saved in `ilps` and `logs` folders.

# Trip data sandbox

Generates a complete trip data sandbox to study pickup and delivery problems.


Change the file `config_tripdata/config_tripdata.json` to choose the region as well as the trip data settings.

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