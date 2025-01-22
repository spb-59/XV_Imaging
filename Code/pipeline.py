import pandas as pd
from sklearn.cluster import KMeans
from sklearn.discriminant_analysis import StandardScaler
import numpy as np
from scipy import stats
import math

def global_clustering_model(controls: list) -> KMeans:
    """
    Perform global clustering based on control samples, returns model that can be used in analysis

    Args:
        controls (list): A list of DataFrames of controls to be used for global clustering.

    Returns:
        KMeans: A KMeans model that can be used to cluster the data points with model.predict()
    """
    #for storing all specific ventilation values
    vent=[]
    for d in controls:
        vent.extend(d['Specific Ventilation (mL/mL)'])

    vent=np.array(vent)

    #model that makes global clusters
    model= KMeans(n_clusters = 6,init = 'k-means++')
    model.fit(vent.reshape(-1, 1))

    return model


def local_clustering(sample:pd.DataFrame)->pd.DataFrame:
    """
    Perform local clustering based on a sample DataFrame.

    Args:
        sample (pd.DataFrame): A DataFrame containing the XV data points to be clustered.

    Returns:
        pd.DataFrame: A DataFrame with an additional column 'lCluster' indicating the cluster assignment for each data point.
    """
    model= KMeans(n_clusters = 6,init = 'k-means++')
    cluster=model.fit_predict(pd.DataFrame(sample['Specific Ventilation (mL/mL)']))

    sample['lCluster']=cluster


    avg_vent=sample.groupby('lCluster')['Specific Ventilation (mL/mL)'].mean()
    sorted_clusters = avg_vent.sort_values().index


    cluster_mapping = {old: new for new, old in enumerate(sorted_clusters)}


    sample['lCluster'] = sample['lCluster'].map(cluster_mapping)


    return sample

def add_clusters(sample:pd.DataFrame,gModel:KMeans)->pd.DataFrame:
    """
    Perform clustering based on a sample DataFrame and a global clustering model.

    Args:
        sample (pd.DataFrame): A DataFrame containing the XV data points to be clustered.
        gModel (KMeans): A KMeans model obtained from global clustering.

    Returns:
        pd.DataFrame: A DataFrame with an additional column 'lCluster' indicating the local cluster assignment and 'gCluster'
        indicating global cluster for each data point.
    """
    #preform global clustering
    cluster=gModel.predict(pd.DataFrame(sample['Specific Ventilation (mL/mL)']))
    sample['gCluster']=cluster
    avg_vent=sample.groupby('gCluster')['Specific Ventilation (mL/mL)'].mean()
    sorted_clusters = avg_vent.sort_values().index


    cluster_mapping = {old: new for new, old in enumerate(sorted_clusters)}


    sample['gCluster'] = sample['gCluster'].map(cluster_mapping)

    #perform local clustering
    sample=local_clustering(sample)


    return sample

def extract_cluster_features(sample:pd.DataFrame,gModel:KMeans)->tuple[pd.DataFrame,np.ndarray]:
    """
    Extract features from a sample using the clustering method

    Args:
        sample (pd.DataFrame): A DataFrame containing the XV data points.
        gModel (KMeans): KMeans model to use for global clustering

    Returns:
        tuple[pd.DataFrame,pd.DataFrame]: A tuple of two DataFrames. The first DataFrame contains the XV data points with an additional
        column 'lCluster' indicating the local cluster assignment and 'gCluster' indicating global cluster for each data point.
        The second DataFrame contains the extracted features.
    """
    # Add global clusters to the sample DataFrame
    og_sample=pd.DataFrame(sample).copy(deep=True)
    sample = add_clusters(sample, gModel)



    #extract the features
    global_features = sample.groupby('gCluster')['Specific Ventilation (mL/mL)'].describe()[['mean']]     
    local_features = sample.groupby('lCluster')['Specific Ventilation (mL/mL)'].describe()[['mean']]     


    local_features.columns = ['l_' + col for col in local_features.columns]
    global_features.columns = ['g_' + col for col in global_features.columns]

    x_mean=sample['x (mm)'].mean()
    y_mean=sample['y (mm)'].mean()
    z_mean=sample['z (mm)'].mean()

    lower_right_front = sample[(sample['x (mm)'] > x_mean) & (sample['y (mm)'] < y_mean) & (sample['z (mm)'] > z_mean)]
    lower_right_back = sample[(sample['x (mm)'] > x_mean) & (sample['y (mm)'] < y_mean) & (sample['z (mm)'] < z_mean)]
    lower_left_front = sample[(sample['x (mm)'] < x_mean) & (sample['y (mm)'] < y_mean) & (sample['z (mm)'] > z_mean)]
    lower_left_back = sample[(sample['x (mm)'] < x_mean) & (sample['y (mm)'] < y_mean) & (sample['z (mm)'] < z_mean)]
    upper_right_front = sample[(sample['x (mm)'] > x_mean) & (sample['y (mm)'] > y_mean) & (sample['z (mm)'] > z_mean)]
    upper_right_back = sample[(sample['x (mm)'] > x_mean) & (sample['y (mm)'] > y_mean) & (sample['z (mm)'] < z_mean)]
    upper_left_front = sample[(sample['x (mm)'] < x_mean) & (sample['y (mm)'] > y_mean) & (sample['z (mm)'] > z_mean)]
    upper_left_back = sample[(sample['x (mm)'] < x_mean) & (sample['y (mm)'] > y_mean) & (sample['z (mm)'] < z_mean)]

    subsets = [
    ('lower_right_front', lower_right_front),
    ('lower_right_back', lower_right_back),
    ('lower_left_front', lower_left_front),
    ('lower_left_back', lower_left_back),
    ('upper_right_front', upper_right_front),
    ('upper_right_back', upper_right_back),
    ('upper_left_front', upper_left_front),
    ('upper_left_back', upper_left_back),
]

    # Initialize feature DataFrame
    local_features = local_features.reset_index()
    global_features = global_features.reset_index()
    features = pd.merge(local_features, global_features, left_on='lCluster', right_on='gCluster', how='outer')

    # Process each subset
    for name, subset in subsets:
        global_subset = subset.groupby('gCluster')['Specific Ventilation (mL/mL)'].describe()[[ '50%', '25%', '75%']]
        local_subset = subset.groupby('lCluster')['Specific Ventilation (mL/mL)'].describe()[[ '50%', '25%', '75%']]
        
        # Add prefixes for quadrant-specific features
        global_subset.columns = [f"{name}_g_" + col for col in global_subset.columns]
        local_subset.columns = [f"{name}_l_" + col for col in local_subset.columns]
        
        global_subset = global_subset.reset_index()
        local_subset = local_subset.reset_index()
        
        # Merge with main features DataFrame
        features = pd.merge(features, global_subset, on='gCluster', how='outer')
        features = pd.merge(features, local_subset, on='lCluster', how='outer')

    features=features.drop(columns=['gCluster','lCluster'])
    features = features.reset_index(drop=True)
    features=features.values.flatten()
    # features=np.append(features,extract_report(og_sample))


    return sample,features

def extract_features_report(sample:pd.DataFrame)->np.ndarray:
    """
    Extract features from a sample like the 4D medical reports in smaller fragments of the lung

    Args:
        sample (pd.DataFrame): A DataFrame containing the XV data points.

    Returns:
        pd.DataFrame: Data frame of features with each row corresponding to a part of the lung
        np.ndarray: A array of features flatten to 1-D from multidimensional matrix

    """

    x_mean=sample['x (mm)'].mean()
    y_mean=sample['y (mm)'].mean()
    z_mean=sample['z (mm)'].mean()

    lower_right_front = sample[(sample['x (mm)'] > x_mean) & (sample['y (mm)'] < y_mean) & (sample['z (mm)'] > z_mean)]
    lower_right_back = sample[(sample['x (mm)'] > x_mean) & (sample['y (mm)'] < y_mean) & (sample['z (mm)'] < z_mean)]
    lower_left_front = sample[(sample['x (mm)'] < x_mean) & (sample['y (mm)'] < y_mean) & (sample['z (mm)'] > z_mean)]
    lower_left_back = sample[(sample['x (mm)'] < x_mean) & (sample['y (mm)'] < y_mean) & (sample['z (mm)'] < z_mean)]
    upper_right_front = sample[(sample['x (mm)'] > x_mean) & (sample['y (mm)'] > y_mean) & (sample['z (mm)'] > z_mean)]
    upper_right_back = sample[(sample['x (mm)'] > x_mean) & (sample['y (mm)'] > y_mean) & (sample['z (mm)'] < z_mean)]
    upper_left_front = sample[(sample['x (mm)'] < x_mean) & (sample['y (mm)'] > y_mean) & (sample['z (mm)'] > z_mean)]
    upper_left_back = sample[(sample['x (mm)'] < x_mean) & (sample['y (mm)'] > y_mean) & (sample['z (mm)'] < z_mean)]

    subsets = [
    ('lower_right_front', lower_right_front),
    ('lower_right_back', lower_right_back),
    ('lower_left_front', lower_left_front),
    ('lower_left_back', lower_left_back),
    ('upper_right_front', upper_right_front),
    ('upper_right_back', upper_right_back),
    ('upper_left_front', upper_left_front),
    ('upper_left_back', upper_left_back),
]

    features=pd.DataFrame()
    for name, subset in subsets:
        newFeat=extract_report(subset)
        
        features = pd.concat([features,pd.DataFrame(newFeat)])




    return features,features.reset_index(drop=True).values.flatten()

def combine_features(cluster_features:pd.DataFrame,report_features:pd.DataFrame=pd.DataFrame(),single:bool=False):
    scaler=StandardScaler()
    label=cluster_features['Label']
    cluster_features=cluster_features.drop(columns=['Label'])
    cluster_features=pd.DataFrame(scaler.fit_transform(cluster_features.values))

    cluster_features['Label']=label
     
    if single:
        return cluster_features
    return pd.concat([cluster_features,pd.DataFrame(report_features)],axis=1)

    
def extract_report(df:pd.DataFrame):
    df.columns=['SV','X','Y','Z']
    mean=df['SV'].mean()
    median=df['SV'].median()
    vdp=len(df[df['SV']<0.6*mean])/len(df)
    



    kurtosis_value = stats.kurtosis(df['SV'])


    q1 = np.percentile(df['SV'], 25)
    q3 = np.percentile(df['SV'], 75)
    iqr = q3 - q1


    het=iqr/mean


    variance_value = np.var(df['SV'])

    return [mean,vdp,het,kurtosis_value,variance_value]




def neighbours(arr,i,j,k):
    
    binary_numbers = []

    binary_numbers.append(arr[i-1][j][k])

    binary_numbers.append(arr[i+1][j][k])

    binary_numbers.append(arr[i][j-1][k])

    binary_numbers.append(arr[i][j+1][k])

    binary_numbers.append(arr[i][j][k-1])

    binary_numbers.append(arr[i][j][k+1])

    return binary_numbers
        

def bin_to_dec(arr,i,j,k, neighbour_list):
    
    binary_result = [1 if num >= arr[i,j,k] else 0 for num in neighbour_list]

    binary_string = ''.join(map(str, binary_result))

    decimal_number = int(binary_string,2)
    
    return decimal_number

def compute_LBP_3D(grid):
    
    count = 0
    
    shape = grid.shape

    histogram = [0] * 64

    for i in range(1, shape[0]-1):

        for j in range(1, shape[1]-1):

            for k in range(1, shape[2]-1):

                neighbour_list = neighbours(grid,i,j,k)  # list of neighbours

                if math.isnan(grid[i,j,k]) or any(math.isnan(x) for x in neighbour_list): # ignore all nan values
                    continue

                decimal_number = bin_to_dec(grid,i,j,k,neighbour_list) # compute LBP and output a decimal number
                
                histogram[decimal_number] += 1
                
                count += 1  # count the total number of points contributing to LBP_3D
                
    return histogram, count

def create_grid(df, grid_size: tuple[int]):
    max_x, max_y, max_z = grid_size
    grid = np.full((max_x+1, max_y+1, max_z+1), np.nan)

    for _ , row in df.iterrows():

        value_column_name = 'SV'
        value = row[value_column_name]
        x = int(row['X'])
        y = int(row['Y'])
        z = int(row['Z'])


        if not np.isnan(value):
            grid[x, y, z] = value
            
    return grid
def create_grid_new(df):
    x_len=len(df['X'].unique())
    y_len=len(df['Y'].unique())
    z_val=sorted(df['Z'].unique())

    obj=[[[None]*len(z_val) for _ in range(y_len)] for _ in range(x_len)]
    obj=np.full((x_len,y_len,len(z_val)),np.nan)
    for i,x in enumerate(sorted(df['X'].unique())):
        for j,y in enumerate(sorted(df['Y'].unique())):
            mask = (df['X'] == x) & (df['Y'] == y)
            if any(mask):
                for k,z in enumerate(z_val):

                    m=(df['X'] == x) & (df['Y'] == y)&(df['Z']==z) 
                    if any(m):
                        obj[i,j,k]=df[m]['SV'].values[0]
    
    return obj

def conv_3d_patch(grid, scale=3): # scale = 3 for 3x3x3 patches
    shape = grid.shape
    new_grid = np.full(shape, np.nan)

    for i in range(shape[0] - 2):
        for j in range(shape[1] - 2):
            for k in range(shape[2] - 2):
                patch = grid[i:i+scale, j:j+scale, k:k+scale]
                if np.all(~np.isnan(patch)):
                    new_grid[i:i+scale, j:j+scale, k:k+scale] = patch
    return new_grid

# This function accept grid and new_grid as 3D array
def remain_percent(grid, new_grid):
    
    # Number of non-NaN in grid
    grid_not_nan = grid.size - np.sum(np.isnan(grid))

    # Number of non-NaN in new_grid
    new_grid_not_nan = new_grid.size - np.sum(np.isnan(new_grid))

    # percentage of remaining points
    percent = new_grid_not_nan/grid_not_nan

    return grid_not_nan, new_grid_not_nan, percent

# Convolution for extracting the removed points
def conv_remain_points(grid, new_grid):
    shape = grid.shape
    removed_points = np.full(shape, np.nan)

    for i in range(shape[0]):
        for j in range(shape[1]):
            for k in range(shape[2]):
                if grid[i,j,k] == new_grid[i,j,k]:
                    pass
                else:
                    removed_points[i,j,k] = grid[i,j,k]
                    
    return removed_points

class LBP_3D():
    def __init__(self,samples):
        self.samples=samples
        x,y,z=-1,-1,-1
        for s in samples:
            x=int(math.ceil(max(x,max(abs(s[0]['X'])))))
            y=int(math.ceil(max(y,max(abs(s[0]['Y'])))))
            z=int(math.ceil(max(z,max(abs(s[0]['Z'])))))
        
        self.gridSize=(x,y,z)
        self.features=pd.DataFrame()

    def extract(self)->pd.DataFrame:
        
        for s in self.samples:
            label=s[1]
            hist,count=compute_LBP_3D(create_grid(s[0],self.gridSize))
            feature=pd.DataFrame([np.array(hist)/count])
            feature['Label']=label
            self.features=pd.concat([self.features, pd.DataFrame(feature)], ignore_index=True)
        
        return self.features

class LBP_3DT():
    def __init__(self,samples):
        self.samples=samples
        x,y,z=-1,-1,-1
        for s in samples:
            x=int(math.ceil(max(x,max(abs(s[0]['X'])))))
            y=int(math.ceil(max(y,max(abs(s[0]['Y'])))))
            z=int(math.ceil(max(z,max(abs(s[0]['Z'])))))
        
        print(x,y,z)
        self.gridSize=(x,y,z)
        self.features=[]

    def extract(self)->pd.DataFrame:
        
        for s in self.samples:
            label=s[1]
            feat=pd.DataFrame()
            for i in range(14):
                df=s[0]
                grid=create_grid_new(df[df['Frame']==i])
                hist,count=compute_LBP_3D(grid)
                feature=pd.DataFrame([np.array(hist)/count])
                feat=pd.concat([feat, pd.DataFrame(feature).T],axis=1, ignore_index=True)
            self.features.append((feat,label))
        
        return self.features

class ClusterFeatures():

    def __init__(self,samples):
        self.samples=samples
        controls=[]
        for s in samples:
            if s[1]==0:
                controls.append(s[0])
        self.g_model=self.get_g_model(controls[:2])
        self.features=pd.DataFrame()


    def get_g_model(self,controls):
        return global_clustering_model(controls)

    def extract(self):

        for s in self.samples:

            _,feature=extract_cluster_features(s[0],self.g_model)
            feature=pd.DataFrame([feature])
            feature['Label']=s[1]
            self.features=pd.concat([self.features, pd.DataFrame(feature)], ignore_index=True)
        
        return self.features

        


    

