from hashlib import sha256
from os import listdir, path, stat, stat_result
from typing import ClassVar
from yaml import safe_load

from .engine import Engine
from .prompt import Prompt
from .rules import Auditor, UnionRuleList
from .utils.typing import Typing
from .utils.version import get_project_version


class Pipeline:
    """
    Pipeline that loads rule files, tracks changes, and runs them on prompts.
    """

    def __init__(self, directory: str | None = None):
        self._cache: dict[str, Tracker] = {}
        self._directory = directory if directory else self._get_base_directory()
        self._version = get_project_version()

    def _get_base_directory(self):
        base_path = path.dirname(__file__)
        full_path = path.join(base_path, "../rules")
        return path.realpath(full_path)

    def _load_and_cache(self):
        print(f"[ComfyUI-MyOriginalWaifu v{self._version}]")
        print(f"→ loading {self._directory}")
        files = listdir(self._directory)

        # Refresh the rules.
        for name in sorted(files):
            if name.endswith(".yml") or name.endswith(".yaml"):
                file_path = path.join(self._directory, name)
                file_stat = stat(file_path)
                file_yaml = self._cache.get(name, None)
                if not file_yaml or not file_yaml.validate(file_stat):
                    print(f"→ caching {file_path}")
                    self._cache[name] = Tracker(file_path, file_stat)

        # Prune old rules from the cache.
        for name in list(self._cache.keys()):
            if name not in files:
                print(f"→ pruning {path.join(self._directory, name)}")
                del self._cache[name]

    def get_cache_key(self, positive: str, negative: str):
        self._load_and_cache()
        hash = sha256()

        # Digest the rule keys.
        for name in sorted(self._cache.keys()):
            for key in self._cache[name].digest():
                hash.update(key.encode("utf-8"))

        # Digest the prompt.
        hash.update(positive.encode("utf-8"))
        hash.update(negative.encode("utf-8"))
        return hash.hexdigest()

    def run(self, positive: Prompt, negative: Prompt):
        self._load_and_cache()
        engine = Engine(positive, negative)

        # Run the rules on the engine.
        for file in sorted(self._cache.keys()):
            self._cache[file].run(engine)

        # Log the output prompt.
        print(f"→ positive: {positive}")
        print(f"→ negative: {negative}")

    # Shared default instance.
    DEFAULT: ClassVar["Pipeline"]


class Tracker:
    """
    Tracker for a rule file that validates file state and runs rules.
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
        print(f"→ running {self._path}")
        if self._rules:
            engine.run(self._rules)

    def validate(self, stat: stat_result):
        same_time = self._stat.st_mtime_ns == stat.st_mtime_ns
        same_size = self._stat.st_size == stat.st_size
        return same_time and same_size


Pipeline.DEFAULT = Pipeline()
