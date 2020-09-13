from model.Request import Request
from pprint import pprint
import pandas as pd
import requests
import os
from multiprocessing import Pool
import osmnx as ox
from functools import partial
import network_gen as nw
from datetime import datetime, timedelta
import random
random.seed(1)

# Stores in key = 'name of experiment' the generator used to
# read trip data in file.
request_base = dict()


def download_file(url, data_path, file_name):
    """Download online file and save it.

    Arguments:
        url {String} -- Url to download
        output_file {String} -- Target path
    """

    output_file = "{}/{}".format(data_path, file_name)

    print("Loading  '{}'".format(output_file))

    if not os.path.exists(output_file):
        # TODO action when url does not exist
        print("Downloading {}".format(url))
        r = requests.get(url, allow_redirects=True)
        open(output_file, 'wb').write(r.content)


def get_trip_data(tripdata_path, output_path, start=None, stop=None):
    """
    Read raw tripdata csv and filter unnecessary info.

        1 - Check if output path exists
        2 - If output path does not exist
            2.1 - Select columns ("pickup_datetime",
                                "passenger_count",
                                "pickup_longitude",
                                "pickup_latitude",
                                "dropoff_longitude",
                                "dropoff_latitude")
            2.2 - If start and stop are not None, get excerpt
        3 - Save clean tripdata in a csv
        3 - Return dataframe

    Arguments:
        tripdata_path {string} -- Raw trip data csv path
        output_path {string} -- Cleaned trip data csv path
        start {string} -- Datetime where tripdata should start 
            (e.g., 2011-02-01 12:23:00)
        stop {string} -- Datetime where tripdata should end
            (e.g., 2011-02-01 14:00:00)

    Returns:
        Dataframe -- Cleaned tripdata dataframe
    """

    print("files:", output_path, tripdata_path)

    # Trip data dataframe (Valentine's day)
    tripdata_dt_excerpt = None

    try:

        # Load tripdata
        tripdata_dt_excerpt = pd.read_csv(
            output_path,
            parse_dates=True,
            index_col="pickup_datetime")

        print("Loading file '{}'.".format(output_path))

    except:

        # Columns used
        filtered_columns = ["pickup_datetime",
                            "passenger_count",
                            "pickup_longitude",
                            "pickup_latitude",
                            "dropoff_longitude",
                            "dropoff_latitude"]

        # Reading file
        tripdata_dt = pd.read_csv(tripdata_path,
                                  parse_dates=True,
                                  index_col="pickup_datetime",
                                  usecols=filtered_columns,
                                  na_values='0')

        tripdata_dt_excerpt = None

        # Get excerpt
        if start and stop:
            tw_filter = (
                (tripdata_dt.index >= start) &
                (tripdata_dt.index <= stop)
            )
            tripdata_dt_excerpt = pd.DataFrame(tripdata_dt.loc[tw_filter])
        else:
            tripdata_dt_excerpt = pd.DataFrame(tripdata_dt)

        # Remove None values
        tripdata_dt_excerpt.dropna(inplace=True)

        # Sort
        tripdata_dt_excerpt.sort_index(inplace=True)

        # Save day data
        tripdata_dt_excerpt.to_csv(output_path)

    return tripdata_dt_excerpt


def get_ids(
        G,
        pk_lat, pk_lon,
        dp_lat, dp_lon,
        distance_dic_m,
        max_dist=50):

    try:
        # Get pick-up and drop-off coordinates of request
        pk = (pk_lat, pk_lon)
        dp = (dp_lat, dp_lon)

        # Get nearest node in graph from coordinates
        n_pk = ox.get_nearest_node(G, pk, return_dist=True)
        n_dp = ox.get_nearest_node(G, dp, return_dist=True)

        #print("Nearest:",n_pk, n_dp)

        # If nearest node is "max_dist" meters far from point, request
        # is discarded
        if n_pk[1] > max_dist or n_dp[1] > max_dist:
            return [None, None]

        # pk must be different of dp
        if n_pk[0] == n_dp[0]:
            return [None, None]

        d = distance_dic_m[n_pk[0]][n_dp[0]]
        #print("Dist:", d)

        # Remove short distances
        if d >= max_dist:
            return [n_pk[0], n_dp[0]]
        else:
            return [None, None]
    except:
        return [None, None]


def add_ids_chunk(G, distance_dic_m, info):
    """Receive a dataframe chunk with tripdata and try adding node ids
    to the pickup and delivery points.


    Arguments:
        G {networkx} -- Street network to performe coordinate/node match
        distance_dic_m {dict{dict(float)}} -- Shortest distances between
            ODs in G (usage: distance_dic_m[o][d] = dist).
        info {dataframe} -- Unmatched tripdata

    Returns:
        dataframe -- Trip data with pickup and delivery node ids from
            graph G.
    """

    # Add pickup and delivery ids
    # If ids can't be found, the trip occurs outside G boundaries
    info[["pk_id", "dp_id"]] = info.apply(
        lambda row: pd.Series(
            get_ids(
                G,
                row['pickup_latitude'],
                row['pickup_longitude'],
                row['dropoff_latitude'],
                row['dropoff_longitude'],
                distance_dic_m
            )
        ),
        axis=1
    )

    original_chunk_size = len(info)

    # Remove trip data outside street network in G
    info.dropna(inplace=True)

    print("Adding ", len(info), "/", original_chunk_size)

    # Convert node ids and passenger count to int
    info[["passenger_count", "pk_id", "dp_id"]] = info[[
        "passenger_count", "pk_id", "dp_id"]].astype(int)

    # Reorder columns
    order = ['pickup_datetime',
             'passenger_count',
             'pk_id', 'dp_id',
             'pickup_latitude',
             'pickup_longitude',
             'dropoff_latitude',
             'dropoff_longitude']

    info = info[order]

    return info


def add_ids(path_tripdata, path_tripdata_ids, G, distance_dic_m):
    """Read large dataframe in chunks of trip data and associate
    node ids from graph G to pickup and delivery coordinates
    (within 50 meters).

    Entries whose coordinates are not matched to any point in G
    are discarded, since their occur outside G boundaries.

    Arguments:
        path_tripdata {str} -- File path of the tripdata.
        path_tripdata_ids {str} -- Target file path of tripdata with
            pickup and delivery ids.
        G {networkx} -- Graph to compare tripdata against.
        distance_dic_m {dict{int:dict{int:float}}} -- Shortest distances
            between ODs in G (usage: distance_dic_m[o][d] = dist).
    """

    dt = None

    # if file does not exist write header
    if os.path.isfile(path_tripdata_ids):

        # Load tripdata
        dt = pd.read_csv(
            path_tripdata_ids,
            parse_dates=True,
            index_col="pickup_datetime"
        )

        print("\nLoading trip data with ids...'{}'.".format(path_tripdata_ids))

    else:

        print("############ NY trip data ", path_tripdata, path_tripdata_ids)
        tripdata = pd.read_csv(path_tripdata)

        tripdata.info()

        # Number of lines to read from huge .csv
        chunksize = 2000

        # Redefine function to add graph and distances
        func = partial(add_ids_chunk, G, distance_dic_m)

        # Total number of chunks to process
        togo = int(len(tripdata)/chunksize)

        # Read chunks of 500 lines
        count = 0
        count_lines = 0

        # Multiprocesses
        n_mp = 8
        p = Pool(n_mp)

        # List of chunks of tripdata to process in parallel
        list_parallel = []

        # Start chunk reading process
        gen_chunks = pd.read_csv(
            path_tripdata,
            index_col=False,
            chunksize=chunksize)

        # Read first batch from dataframe and save in list
        # for parallel processing
        next_batch = next(gen_chunks)
        list_parallel.append(next_batch)

        # If first batch was read successfully, continue reading
        # following batches
        while next_batch is not None:

            try:
                next_batch = next(gen_chunks)
                list_parallel.append(next_batch)
            except:
                next_batch = None

            # The pool of processes starts if:
            #  - The number of dataframe chunks is equal to the
            #    max number of multiprocesses;
            #  - The end of the dataframe was reached (no next batch).
            if len(list_parallel) == n_mp or next_batch is None:

                # Update progress counters
                count = count + len(list_parallel)
                count_lines = count_lines + sum(map(len, list_parallel))

                # Start multiprocessing
                chunks_with_ids = p.map(func, list_parallel)

                # Writing chunks in target file
                for info_ids in chunks_with_ids:

                    # if file does not exist write header
                    if not os.path.isfile(path_tripdata_ids):

                        info_ids.to_csv(path_tripdata_ids,
                                        index=False)

                    # Since file exists, append without writing
                    # the header
                    else:
                        info_ids.to_csv(path_tripdata_ids,
                                        mode="a",
                                        header=False,
                                        index=False)

                # Clean parallel list to add more chunks
                list_parallel.clear()

                print(
                    (
                        "Chunk progress: {}/{}"
                        " - Dataframe progress: {}/{}"
                    )
                    .format(count, togo, count_lines, len(tripdata))
                )

        # Load tripdata
        dt = pd.read_csv(
            path_tripdata_ids,
            parse_dates=True,
            index_col="pickup_datetime")

        print(
            (
                "\nLoading trip data with ids"
                " (after processing)...'{}'."
            )
            .format(path_tripdata_ids)
        )

    print(dt.head())
    print(dt.describe())


def get_random_request_series(series, od, max_passenger_count):
    """Create a series for the request data that will be integrated
    in the OD dataframe.

    Arguments:
        series {[type]} -- [description]
        od {[type]} -- [description]
        max_passenger_count {[type]} -- [description]

    Returns:
        [type] -- [description]
    """

    data = dict(series)
    data['passenger_count'] = random.randint(1, max_passenger_count)
    data.update(od)
    return pd.Series(data)


def gen_random_vehicle_origin(G):

    n_nodes = nw.get_number_of_nodes(G)

    return random.randint(0, n_nodes-1)


def gen_random_request_od(
        G,
        min_dist=100,
        max_dist=1000000,
        distance_dic=None):
    """Generate a single request by choosing random ODs from
    the street network G.

    The distance between ODs is in the range [min_dist, max_dist]

    Arguments:
        min_dist {float} -- Minimum distance between request's OD
            (default = meters)
        max_dist {float} -- Maximum distance between request's OD
            (default = meters)
        G {networkx} -- Graph to get node coordinates.
        distance_dic {dict{int:dict{int:float}}} -- Shortest distances
            between ODs in G (usage: distance_dic_m[o][d] = dist).

    Returns:
        dict -- Random request dictionary. Details:
        'pickup_longitude', 'pickup_latitude', 'dropoff_longitude',
        'dropoff_latitude', 'pk_id', 'dp_id'.
    """

    n_nodes = nw.get_number_of_nodes(G)

    while True:
        # Find random origin and destination
        o = random.randint(0, n_nodes-1)
        d = random.randint(0, n_nodes-1)
        dist = (distance_dic[o][d]
                if distance_dic else nw.get_distance(G, o, d))
        # Stop searching if adequate destination is found
        if o != d \
                and dist >= min_dist \
                and dist <= max_dist:
            break

    x_from = G.node[o]["x"]
    y_from = G.node[o]["y"]
    x_to = G.node[d]["x"]
    y_to = G.node[d]["y"]

    req = {'pickup_longitude': x_from,
           'pickup_latitude': y_from,
           'dropoff_longitude': x_to,
           'dropoff_latitude': y_to,
           'pk_id': o,
           'dp_id': d}

    return req


def get_next_batch(
        experiment_name,
        chunk_size=2000,
        batch_size=30,
        tripdata_csv_path=None,
        start_timestamp=None,
        end_timestamp=None,
        classes=None,
        freq=None):
    """
    Iteratevely returns trip data within sequential time intervals 
    for each experiment.

    Each experiment is associated to a dictionary entry 
    containing a generator that reads trip data chunks from 
    a csv iteratively.


    generator 
     - CSV reader
     - First tim of size "batch_size"

    Arguments:
        experiment_name {[type]} -- Name experiment calling 
        the batch of requests.

    Keyword Arguments:
        chunk_size {int} -- N. of lines read from dataframe 
                            each time (default: {2000})
        batch_size {int} -- Data interval returned each call
                             (default: {30})
        tripdata_csv_path {str} -- Origin of trip data (default: {None})
        start_timestamp {str} -- Earliest time of tripdata 
                                (e.g., 2011-02-01 00:00:00) (default: {None})
        end_timestamp {str} -- Latest time of tripdata 
                                (e.g., 2011-02-10 00:00:00) (default: {None})

    Returns:
        dataframe -- trip data slice corresponding to the sequence 
        in current time interval
    """

    # Easy access to dictionary reffering to experiment_name
    trips = None

    # Start chunk reading process from the beginning if experiment
    # is being run for the first time
    if experiment_name not in request_base:

        print(("\nActivating tripdata generator"
               " for experiment '{}'...").format(experiment_name))

        # Generator of data chunks from csv file
        gen_chunks = pd.read_csv(
            tripdata_csv_path,
            parse_dates=True,
            index_col="pickup_datetime",
            chunksize=chunk_size)

        # Save generator and related information in dictionary
        trips = request_base[experiment_name] = dict()

        trips['generator'] = gen_chunks

        # When requests start being read
        trips['start_time'] = datetime.strptime(
            start_timestamp,
            '%Y-%m-%d %H:%M:%S')

        # When requests stop being read
        trips['final_time'] = datetime.strptime(
            end_timestamp,
            '%Y-%m-%d %H:%M:%S')

        # Determine where generator last stopped reading
        trips['current_time'] = datetime.strptime(
            start_timestamp,
            '%Y-%m-%d %H:%M:%S')

        # Interval pulled from request base each time (e.g., 30s)
        trips['batch_size'] = timedelta(seconds=batch_size)

        trips['tripdata_csv_path'] = tripdata_csv_path

        # Store read requests outside current interval (due to chunk size)
        trips['residual_requests'] = None

        trips['service_classes'] = classes
        trips['class_frequencies'] = freq

        # Loop data until batch has info > start_timestamp
        for first_batch in trips['generator']:

            if not first_batch[start_timestamp:].empty:
                # The first batch goes to the residual request
                trips['residual_requests'] = first_batch
                break
    else:
        # The experiment has already been initiated.
        # Load previous data.
        trips = request_base[experiment_name]

    # If last possible time was reached, stop returning data
    if trips['current_time'] >= trips['final_time']:
        return None

    batch = trips['residual_requests']
    left_tw = trips['current_time']
    right_tw = left_tw + trips['batch_size']
    #print(left_tw, "--", right_tw)
    right_tw = min(right_tw, trips['final_time'])

    for next_batch in trips['generator']:

        batch = batch.append(next_batch)

        if not batch[right_tw:].empty:
            break

        #print('Size batch after:', len(batch))

    # Stores requests read (due to the chunk size) but not returned
    trips['residual_requests'] = pd.DataFrame(batch[right_tw:])

    # Cut dataframe until time "right_tw" (not included)
    batch = batch[: right_tw - timedelta(seconds=1)]

    # Update current time
    trips['current_time'] = right_tw

    # Randomly assign user classes to requests if
    # service classes were defined
    if trips['service_classes']:
        service_class_distribution = random.choices(
            trips['service_classes'],
            weights=trips['class_frequencies'],
            k=len(batch)
        )

        batch['service_class'] = pd.Series(
            service_class_distribution,
            index=batch.index
        )

    return batch


def random_tw(min_date, max_date, lenght_sec):
    minutes = max_date - min_date
    rounds = int(minutes.total_seconds()/lenght_sec)
    random_round = random.randint(0, rounds)
    earliest = min_date + \
        timedelta(seconds=random.randint(0, rounds)*lenght_sec)
    latest = earliest + timedelta(seconds=lenght_sec)
    return earliest, latest


def get_trips(n, df, min_date, max_date, tw_lenght_sec, first_date=None):
    df_cut = pd.DataFrame()
    while(len(df_cut) < n):
        e, l = random_tw(min_date, max_date, tw_lenght_sec)
        low = df.index >= e
        high = df.index < l
        df_cut = df[low & high]

        if first_date:
            diff = e - first_date
            df_cut.index = df_cut.index - diff
    df_sample = df_cut.sample(n=n, replace=False)
    return df_sample.sort_index()


def create_instances_exact_sol(
        area,
        demand_size_list,
        user_base_segmentation_dict,
        tripdata_csv_path,
        target_folder,
        min_datetime_str=None,
        repeat=1,
        uniform_passenger_count=None):

    df = pd.read_csv(
        tripdata_csv_path,
        parse_dates=True,
        index_col="pickup_datetime",
    )
    min_date = min(df.index)
    max_date = max(df.index)

    if min_datetime_str:
        min_datetime = datetime.strptime(
            min_datetime_str,
            '%Y-%m-%d %H:%M:%S'
        )

        min_date = max(min_date, min_datetime)
        df = df[df.index >= min_datetime_str]
        print("SET MINDATE:", min_datetime)


    for i in range(1, repeat+1):
        for demand_size in demand_size_list:
            for ub_label, ub_freq_dict in user_base_segmentation_dict.items():

                freq_info = "_".join(
                    [
                        "{}-{}".format(user_class, int(freq*100))
                        for user_class, freq in ub_freq_dict.items()
                    ]
                )

                file_name = "{area}__{demand:03}__{ub_label}__{freq}__{id:003}__{p_count}".format(
                    id=i,
                    area=area,
                    demand=demand_size,
                    ub_label=ub_label,
                    freq=freq_info,
                    p_count=(
                        'maxpcount_{:02}'.format(uniform_passenger_count)
                        if uniform_passenger_count else 'maxpcount_legacy'
                    )
                )

                df_requests = get_n_requests_df(
                    demand_size,
                    df,
                    min_date,
                    max_date,
                    tripdata_csv_path=tripdata_csv_path,
                    class_freq_dict=ub_freq_dict
                )

                if uniform_passenger_count is not None:
                    df_requests['passenger_count'] = uniform_passenger_count

                path_csv = "{}/{}.csv".format(
                    target_folder, file_name
                )

                print("Saving at '{}'".format(path_csv))
                df_requests.to_csv(path_csv, date_format='%Y-%m-%d %H:%M:%S')


def get_n_requests_df(
        number_requests,
        df,
        min_date,
        max_date,
        tripdata_csv_path=None,
        start_timestamp=None,
        end_timestamp=None,
        class_freq_dict=None):

    trips = get_trips(number_requests, df, min_date, max_date, 30, first_date=min_date)

    population, frequencies = zip(*class_freq_dict.items())

    service_class_distribution = random.choices(
        population,
        weights=frequencies,
        k=len(trips)
    )

    trips['service_class'] = pd.Series(
        service_class_distribution,
        index=trips.index
    )

    return trips


def gen_requests(
        clone_tripdata_path,
        max_passenger_count,
        G,
        output_path,
        start_timestamp=None,
        end_timestamp=None,
        min_dist=None,
        max_dist=None,
        distance_dic=None):

    print("\nGeneration random requests clone mirror...")

    # if file does not exist write header
    if os.path.isfile(output_path):
        print("\nTrip data already exists in '{}'.".format(output_path))
        return
    else:

        print("Saving at '{}'.".format(output_path))

        # Number of lines to read from huge .csv
        chunksize = 2000

        # Start chunk reading process
        gen_chunks = pd.read_csv(
            clone_tripdata_path,
            parse_dates=True,
            index_col="pickup_datetime",
            chunksize=chunksize)

        count = 0
        print("Time window:", start_timestamp, "----", end_timestamp)

        for chunk_dt_clone in gen_chunks:

            chunk_dt_clone = chunk_dt_clone[
                start_timestamp:
                end_timestamp]

            if len(chunk_dt_clone) == 0:
                break

            chunk_dt = chunk_dt_clone.apply(
                lambda row:
                get_random_request_series(
                    row,
                    gen_random_request_od(G, distance_dic=distance_dic),
                    max_passenger_count
                ),
                axis=1
            )

            # Convert node ids and passenger count to int
            chunk_dt[["passenger_count", "pk_id", "dp_id"]] = chunk_dt[[
                "passenger_count", "pk_id", "dp_id"]].astype(int)

            # print(chunk_dt.head())

            # if file does not exist write header
            #print("Saving first chunk...")
            if not os.path.isfile(output_path):

                chunk_dt.to_csv(output_path)

            # Since file exists, append without writing the header
            else:
                chunk_dt.to_csv(output_path,
                                mode="a",
                                header=False)

            count = count + 1
            print(
                "Chunk progress: {}----{}".format(
                    chunk_dt.iloc[0].name,
                    chunk_dt.iloc[-1].name
                )
            )

    # dt_start_ts = datetime.strptime(start_timestamp, '%Y-%m-%d %H:%M:%S')
    # dt_end_ts = datetime.strptime(end_timestamp, '%Y-%m-%d %H:%M:%S')
    # td_batch_duration = timedelta(seconds=batch_duration_s)

    # current_dt = dt_start_ts

    # while current_dt < dt_end_ts:
    #     current_dt = current_dt + td_batch_duration
    #     print(dt_start_ts, current_dt, dt_end_ts)

    # TODO Use frequency generation in the future. Example:
    # date_rng = pd.date_range(start='1/1/2018', end='1/08/2018', freq='H')


if __name__ == "__main__":
    pass
    # Get network graph and save
    # G = nw.get_network_from(config.tripdata["region"],
    #                          config.data_path,
    #                          config.graph_name,
    #                          config.graph_file_name)
    # nw.save_graph_pic(G)

    # print( "\nGetting distance data...")
    # # Creating distance dictionary [o][d] -> distance
    # distance_dic = nw.get_distance_dic(config.path_dist_dic, G)
