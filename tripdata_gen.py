import pandas as pd
import requests
import os
from multiprocessing import Pool
import osmnx as ox
from functools import partial
import network_gen as nw


def download_file(url, root_path, file_name):
    """Download online file and save it.

    Arguments:
        url {String} -- Url to download
        output_file {String} -- Target path
    """

    output_file = "{}/{}".format(root_path, file_name)

    print("Laoding  '{}'".format(output_file))

    if not os.path.exists(output_file):
        print("Downloading {}".format(url))
        r = requests.get(url, allow_redirects=True)
        open(output_file, 'wb').write(r.content)


def get_trip_data(root_path, tripdata_filename, output_filename, start, stop):

    # Output filepath
    output_path = "{}/{}.csv".format(root_path, output_filename)
    tripdata_path = "{}/{}".format(root_path, tripdata_filename)

    print("files:", output_path, tripdata_path)

    # Trip data dataframe (Valentine's day)
    tripdata_dt_excerpt = None

    try:

        # Load tripdata
        tripdata_dt_excerpt = pd.read_csv(
            output_path, parse_dates=True, index_col="pickup_datetime")

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

        # Get valentine's day data
        tripdata_dt_excerpt = pd.DataFrame(
            tripdata_dt.loc[(tripdata_dt.index >= start) & (tripdata_dt.index <= stop)])

        # Remove None values
        tripdata_dt_excerpt.dropna(inplace=True)

        # Sort
        tripdata_dt_excerpt.sort_index(inplace=True)

        # Save day data
        tripdata_dt_excerpt.to_csv(output_path)

    return tripdata_dt_excerpt


def get_ids(G,
            pk_lat,
            pk_lon,
            dp_lat,
            dp_lon,
            distance_dic_m,
            max_dist=50):

    try:
        # Get pick-up and drop-off coordinates of request
        pk = (pk_lat, pk_lon)
        dp = (dp_lat, dp_lon)

        # Get nearest node in graph from coordinates
        n_pk = ox.get_nearest_node(G, pk, return_dist=True)  # (id, dist)
        n_dp = ox.get_nearest_node(G, dp, return_dist=True)  # (id, dist)

        #print("Nearest:",n_pk, n_dp)

        # If nearest node is "max_dist" meters far from point, request is discarded
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

    info[["pk_id", "dp_id"]] = info.apply(lambda row: pd.Series(get_ids(G,
                                                                        row['pickup_latitude'],
                                                                        row['pickup_longitude'],
                                                                        row['dropoff_latitude'],
                                                                        row['dropoff_longitude'],
                                                                        distance_dic_m)), axis=1)

    n = len(info)
    # Remove trip data outside Manhattan (street network in G)
    info.dropna(inplace=True)

    print("Adding ", len(info), "/", n)

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


def add_ids(file_name, tripdata_filename, root_path, G, distance_dic_m):

    path_tripdata = "{}/{}.csv".format(root_path, tripdata_filename)
    file_path_out = "{}/{}.csv".format(root_path, file_name)

    print("############ NY trip data ", path_tripdata, file_path_out)
    tripdata = pd.read_csv(path_tripdata)

    tripdata.info()

    # Number of lines to read from huge .csv
    chunksize = 500

    # Redefine function to add graph and distances
    func = partial(add_ids_chunk, G, distance_dic_m)

    # Total number of lines
    togo = int(len(tripdata)/chunksize)

    # Read chunks of 500 lines
    # NY data filtered
    count = 0
    count_lines = 0

    # Multiprocesses
    n_mp = 4
    p = Pool(n_mp)

    list_parallel = []

    gen_chunks = pd.read_csv(
        path_tripdata, index_col=False, chunksize=chunksize)

    next_batch = next(gen_chunks)
    list_parallel.append(next_batch)

    while next_batch is not None:

        try:
            next_batch = next(gen_chunks)
            list_parallel.append(next_batch)
        except:
            next_batch = None

        # if info < chunksize, end reached. Process whatever is in parallel list
        if len(list_parallel) == n_mp or next_batch is None:

            count = count + len(list_parallel)
            count_lines = count_lines + sum(map(len, list_parallel))

            chunks_with_ids = p.map(func, list_parallel)

            for info_ids in chunks_with_ids:

                # if file does not exist write header
                if not os.path.isfile(file_path_out):

                    info_ids.to_csv(file_path_out,
                                    index=False)

                # else it exists so append without writing the header
                else:
                    info_ids.to_csv(file_path_out,
                                    mode="a",
                                    header=False,
                                    index=False)

            list_parallel.clear()
            print(count, "/", togo, " (", count_lines, "/", len(tripdata), ")")

    print("############ Manhattan trip data")

    dt = pd.read_csv(file_path_out).info()
    #dt.sort_index(inplace=True)
    #dt.to_csv(file_path_out, index=False)


def process_trip_data(root_path, excerpt_name, start, stop, G=None, cut=False):

    # TLC Taxicab Feb 2011
    file_url = "https://s3.amazonaws.com/nyc-tlc/trip+data/yellow_tripdata_2011-02.csv"
    tripdata_filename = file_url.split("/")[-1]

    # Tripdata root
    root_tripdata = root_path + "/tripdata"
    if not os.path.exists(root_tripdata):
        os.makedirs(root_tripdata)

    # Download trip data if not exists
    download_file(file_url, root_tripdata, tripdata_filename)

    # Get excerpt (start, stop)
    if cut:
        dt_tripdata = get_trip_data(
            root_tripdata, tripdata_filename, excerpt_name, start, stop)

    # If network is given, save file with network ids
    if G:

        distance_dic_m = nw.get_distance_dic(G, root_path)
        # Adding ids to user locations
        add_ids(excerpt_name+"_ids", excerpt_name,
                root_tripdata, G, distance_dic_m)
