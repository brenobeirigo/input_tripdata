import os

import pandas as pd

import config
import tripdata_gen as gen
from model.Request import Request

if __name__ == "__main__":

    print("Trip data:", config.tripdata_csv_path)
    print("Folder instances:", config.root_static_instances_experiments)

    # ******************************************************************
    # Create all instances *********************************************
    # ******************************************************************

    gen.create_instances_exact_sol(
        config.area_tripdata,
        config.demand_sizes,
        config.user_segmentation_dict,
        config.tripdata_csv_path,
        config.root_static_instances_experiments,
        config.min_datetime,
        repeat=config.repeat,
        uniform_passenger_count=config.uniform_passenger_count
    )

    # ******************************************************************
    # Reading instances created ****************************************
    # ******************************************************************

    print("### Reading instances created...")

    # Example of file name: 'city__010__BB__A-16_B-68_C-16.csv'
    folder = config.root_static_instances_experiments
    for file in os.listdir(folder):

        print(f" - \"{file}\"")

        # Removing extension
        base_name = file[:-4]

        # Get instance info from file path
        (area, demand_size, user_base_label, class_freq, id_instance, passenger_count) = base_name.split(
            "__")
        class_freq_pairs = [
            tuple(pair.split('-'))
            for pair in class_freq.split("_")
        ]

        print(area, demand_size, user_base_label,
              class_freq_pairs, id_instance, passenger_count)
        file_path = "{}/{}".format(folder, file)
        df = pd.read_csv(
            file_path,
            parse_dates=True,
            index_col="pickup_datetime"
        )

        requests = Request.df_to_request_list(df, config.service_level)

        print("### Request list created from instances:")
        for r in requests:
            print(r.get_info())
