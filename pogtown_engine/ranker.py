from dataclasses import dataclass,field
import math,json
FEATURES=["fact_integrity","character_specificity","reframe","fertility","novelty","compression"]
@dataclass
class LinearPreferenceRanker:
    weights:dict=field(default_factory=lambda:{k:0. for k in FEATURES});bias:float=0.
    def score(self,g):
        z=self.bias+sum(self.weights.get(k,0)*g.dimensions.get(k,0) for k in FEATURES)
        return 1/(1+math.exp(-max(-30,min(30,z))))
    def fit_pairwise(self,pairs,epochs=120,lr=.08):
        for _ in range(epochs):
            for a,b,y in pairs:
                x={k:a.dimensions.get(k,0)-b.dimensions.get(k,0) for k in FEATURES};z=sum(self.weights[k]*x[k] for k in FEATURES)
                pred=1/(1+math.exp(-max(-30,min(30,z))));err=y-pred
                for k in FEATURES:self.weights[k]+=lr*err*x[k]
        return self
