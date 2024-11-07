from enum import Enum, auto

class Model(Enum):
    STRONG = auto()  # For complex reasoning tasks
    WEAK = auto()    # For simpler tasks
    EMBEDDING = auto() # For generating embeddings
