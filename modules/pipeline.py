from hashlib import sha256
from os import listdir, path, stat, stat_result

from yaml import safe_load

from .engine import Engine
from .prompt import RegionPrompt
from .rules import Auditor, UnionRuleList
from .utils.project import get_project_info
from .utils.typing import Typing


class _File:
    """
    Loads a rule file, tracks changes, and runs the rules on prompts.
    """

    def __init__(self, file_path: str, file_stat: stat_result):
        self._path = file_path
        self._rules = self._parse(file_path)
        self._stat = file_stat

    def _parse(self, file_path: str):
        with open(file_path, "rb") as file_stream:
            auditor = Auditor(path.basename(file_path))
            nodes = safe_load(file_stream)
            if not nodes:
                return None
            elif not Typing.is_list(nodes):
                auditor.fail("yaml must be a list")
            else:
                return UnionRuleList(auditor, nodes)

    def digest(self):
        yield self._path
        yield str(self._stat.st_mtime_ns)
        yield str(self._stat.st_size)

    def run(self, engine: Engine):
        print(f"→ {self._path}")
        if self._rules:
            engine.run(self._rules)

    def validate(self, stat: stat_result):
        same_time = self._stat.st_mtime_ns == stat.st_mtime_ns
        same_size = self._stat.st_size == stat.st_size
        return same_time and same_size


class Pipeline:
    """
    Pipeline that loads rule files and runs rules on prompts.
    """

    def __init__(self, directory: str | None = None):
        self._cache: dict[str, _File] = {}
        self._directory = directory if directory else self._get_base_directory()
        self._displayName, self._version = get_project_info()

    def _get_base_directory(self):
        base_path = path.dirname(__file__)
        full_path = path.join(base_path, "../rules")
        return path.realpath(full_path)

    def _load_and_cache(self):
        files = listdir(self._directory)
        file_set = set(files)

        # Refresh the rules.
        for name in sorted(files):
            if name.endswith(".yml") or name.endswith(".yaml"):
                file_path = path.join(self._directory, name)
                file_stat = stat(file_path)
                file_yaml = self._cache.get(name, None)
                if not file_yaml or not file_yaml.validate(file_stat):
                    self._cache[name] = _File(file_path, file_stat)

        # Prune old rules from the cache.
        for name in list(self._cache.keys()):
            if name not in file_set:
                del self._cache[name]

    def get_cache_key(self, positive: str, negative: str):
        self._load_and_cache()
        hash = sha256()

        # Digest the rule keys.
        for name in sorted(self._cache.keys()):
            for key in self._cache[name].digest():
                hash.update(key.encode("utf-8"))

        # Digest the input prompt.
        hash.update(positive.encode("utf-8"))
        hash.update(negative.encode("utf-8"))
        return hash.hexdigest()

    def run(self, positive: RegionPrompt, negative: RegionPrompt):
        print(f"[{self._displayName} v{self._version}]")
        print(f"← positive: {positive}")
        print(f"← negative: {negative}")
        print(f"→ {self._directory}")
        self._load_and_cache()

        # Check the rules.
        if not any(self._cache):
            print("x skipped (rules not found)")
            return

        # Determine the mode.
        region_count = max(len(positive), len(negative))
        multi_region = region_count > 1

        # Run the rules on each region.
        for index in range(region_count):
            positive_region = positive.get_or_create(index)
            negative_region = negative.get_or_create(index)
            engine = Engine(positive_region, negative_region)

            # Log the region.
            if multi_region:
                print(f"[Region #{index}]")
                print(f"← positive: {positive_region}")
                print(f"← negative: {negative_region}")

            # Run the rules on the region.
            for file in sorted(self._cache.keys()):
                self._cache[file].run(engine)

            # Log the region output.
            print(f"→ positive: {positive_region}")
            print(f"→ negative: {negative_region}")

        # Log the output.
        if multi_region:
            print(f"[Regions #0-{region_count - 1}]")
            print(f"→ positive: {positive}")
            print(f"→ negative: {negative}")

    # Shared default instance.
    DEFAULT: "Pipeline"


Pipeline.DEFAULT = Pipeline()
