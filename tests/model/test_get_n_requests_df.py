import os
import sys

# Adding project folder
root = os.getcwd().replace("\\", "/")
sys.path.append(root)

import tripdata_gen as gen

if __name__ == "__main__":


    tripdata_csv_path='D:/bb/sq/data/delft-south-holland-netherlands/tripdata/random_clone_tripdata_excerpt_2011-02-01_000000_2011-02-02_000000_ids.csv'

    NUMBER_REQUESTS = 100
    bb_segmentation = {
        "A": 0.16,
        "B": 0.68,
        "C": 0.16
    }

    df = gen.get_n_requests_df(
        NUMBER_REQUESTS,
        tripdata_csv_path='D:/bb/sq/data/delft-south-holland-netherlands/tripdata/random_clone_tripdata_excerpt_2011-02-01_000000_2011-02-02_000000_ids.csv',
        class_freq_dict=bb_segmentation)

    print(df)
    print(df.head(10))
    print({sq_class: "{:.2%}".format(freq/NUMBER_REQUESTS)
           for sq_class, freq in df.service_class.value_counts().items()})
