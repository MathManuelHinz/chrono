from typing import List,Dict,TypeVar,Tuple
import networkx as nx
from functools import reduce

X=TypeVar("X")

def subset(l1:List[X],l2:List[X])->bool:
    return reduce(lambda a,b: a and b, [(e in l2) for e in l1], True)

def monotone_clustering(G:nx.Graph, filter_function:Dict[X,bool])->List[List[X]]:
    G_prime:nx.Graph=G.subgraph(filter(lambda x:filter_function[x],list(nx.nodes(G))))
    return [list(cc) for cc in nx.connected_components(G_prime)]

def gbl(G:nx.Graph,f:Dict[X,float],rho:float): return monotone_clustering(G,{x:(f[x]>=rho) for x in f.keys()})

def gbl_get_split_force(G:nx.Graph,f:Dict[X,float])->Tuple[float,List[List[X]],List[List[int]]]:
    sorted_f=sorted([(key,f[key]) for key in f.keys()],key=lambda x:x[1])
    sorted_filtered_f=[sorted_f[0]]
    for key,value in sorted_f:
        if not (sorted_filtered_f[-1][1]==value): sorted_filtered_f.append((key,value))
    n=len(sorted_filtered_f)
    ccs=[(value,gbl(G,f,value)) for key,value in sorted_filtered_f]
    Events:List[List[int]]=[[len([1 for upper_cluster in ccs[i+1][1] if subset(upper_cluster,lower_cluster)]) for lower_cluster in ccs[i][1]] for i in range(n-1)]
    has_split=[max(Events[i])>2 for i in range(len(Events))]
    index=n-2
    for _ in range(n-1):
        if not has_split[index]:
            index-=1
        else:
            break
    return ccs[index+1][0],ccs[index+1][1], Events
   

def gbl_get_ccs(G:nx.Graph,f:Dict[X,float])->List[Tuple[float,List[List[X]]]]:
    sorted_f=sorted([(key,f[key]) for key in f.keys()],key=lambda x:x[1])
    sorted_filtered_f=[sorted_f[0]]
    for key,value in sorted_f:
        if not (sorted_filtered_f[-1][1]==value): sorted_filtered_f.append((key,value))
    n=len(sorted_filtered_f)
    ccs=[(value,gbl(G,f,value)) for key,value in sorted_filtered_f]
    return ccs

if __name__ == "__main__":
    G=nx.Graph()
    G.add_edge("a","b")
    G.add_edge("b","c")
    filter_function={"a":True,"b":False,"c":True}
    print(monotone_clustering(G,filter_function))
    print(gbl(G,{"a":2,"b":0,"c":1},0.5))
    print(gbl_get_split_force(G,{"a":2,"b":0,"c":1}))