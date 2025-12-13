from time import time

from .pipeline import Pipeline
from .prompt import RegionPrompt


begin = time()
positive = RegionPrompt("1girl, celica, smile")
negative = RegionPrompt("")
Pipeline.DEFAULT.run(positive, negative)
print(f"finished in {time() - begin:.2g}s")
