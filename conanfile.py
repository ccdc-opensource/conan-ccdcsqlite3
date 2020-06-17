import os
from conans import ConanFile, CMake, tools


class CCDCConanSqlite3(ConanFile):
    name = "ccdcsqlite3"
    description = "CCDC customised version of sqlite."
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://www.sqlite.org"
    topics = ("conan", "sqlite", "database", "sql", "serverless")
    license = "Public Domain"
    generators = "cmake"
    settings = "os", "compiler", "arch", "build_type"
    exports_sources = ["CMakeLists.txt"]
    options = {"shared": [True, False],
               "fPIC": [True, False],
               "threadsafe": [0, 1, 2],
               "enable_column_metadata": [True, False],
               "enable_explain_comments": [True, False],
               "enable_fts3": [True, False],
               "enable_fts4": [True, False],
               "enable_fts5": [True, False],
               "enable_json1": [True, False],
               "enable_rtree": [True, False],
               "omit_load_extension": [True, False],
               "enable_unlock_notify": [True, False],
               "disable_gethostuuid": [True, False],
               "build_executable": [True, False],
               "enable_null_trim": [True, False],
               "max_column": "ANY",
               }
    default_options = {"shared": False,
                       "fPIC": True,
                       "threadsafe": 1,
                       "enable_column_metadata": True,
                       "enable_explain_comments": False,
                       "enable_fts3": False,
                       "enable_fts4": False,
                       "enable_fts5": False,
                       "enable_json1": False,
                       "enable_rtree": True,
                       "omit_load_extension": False,
                       "enable_unlock_notify": True,
                       "disable_gethostuuid": False,
                       "build_executable": True,
                       "enable_null_trim": False,
                       "max_column": "2000", # default according to https://www.sqlite.org/limits.html#max_column
                       }

    _cmake = None

    @property
    def _source_subfolder(self):
        return "source_subfolder"

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def configure(self):
        del self.settings.compiler.libcxx
        del self.settings.compiler.cppstd

    def source(self):
        tools.get(**self.conan_data["sources"][self.version])
        url = self.conan_data["sources"][self.version]["url"]
        archive_name = os.path.basename(url)
        archive_name = os.path.splitext(archive_name)[0]
        os.rename(archive_name, self._source_subfolder)
        # See BZ 17772 (now JIRA CPP-1008)
        for filename in ['sqlite3.h', 'sqlite3.c']:
            filename = os.path.join(self._source_subfolder, filename)
            with open(filename, 'r') as f:
                text = f.read()

            function_names = []
            import re
            for match in re.finditer(r'SQLITE_API .*(sqlite3_\w+)[;\[\(]', text):
                function_names.append(match.group(1))

            split_string = '#define _SQLITE3_H_'
            split_point = text.find(split_string)
            if split_point == -1:
                split_string = '#define SQLITE3_H'
                split_point = text.find(split_string)
                if split_point == -1:
                    raise RuntimeError("Can't find " + split_string + " in sqlite header file")

            split_point += len(split_string)

            redefined_functions = '\n'.join([
                '#define ' + f + ' ccdc_' + f for f in sorted(set(function_names))
            ])

            text = text[:split_point] + '\n\n' + redefined_functions + '\n\n' + text[split_point:]

            with open(filename, 'w') as f:
                f.write(text)
        for function in [
            "sqlite3_win32_unicode_to_utf8",
            "sqlite3_win32_mbcs_to_utf8_v2",
            "sqlite3_win32_utf8_to_mbcs_v2",
            "sqlite3_win32_utf8_to_unicode",
        ]:
            tools.replace_in_file("source_subfolder/shell.c", function, "ccdc_" + function)

    def _configure_cmake(self):
        if self._cmake:
            return self._cmake
        self._cmake = CMake(self)
        self._cmake.definitions["SQLITE3_BUILD_EXECUTABLE"] = self.options.build_executable
        self._cmake.definitions["THREADSAFE"] = self.options.threadsafe
        self._cmake.definitions["ENABLE_COLUMN_METADATA"] = self.options.enable_column_metadata
        self._cmake.definitions["ENABLE_EXPLAIN_COMMENTS"] = self.options.enable_explain_comments
        self._cmake.definitions["ENABLE_FTS3"] = self.options.enable_fts3
        self._cmake.definitions["ENABLE_FTS4"] = self.options.enable_fts4
        self._cmake.definitions["ENABLE_FTS5"] = self.options.enable_fts5
        self._cmake.definitions["ENABLE_JSON1"] = self.options.enable_json1
        self._cmake.definitions["ENABLE_RTREE"] = self.options.enable_rtree
        self._cmake.definitions["OMIT_LOAD_EXTENSION"] = self.options.omit_load_extension
        self._cmake.definitions["SQLITE_ENABLE_UNLOCK_NOTIFY"] = self.options.enable_unlock_notify
        self._cmake.definitions["HAVE_FDATASYNC"] = True
        self._cmake.definitions["HAVE_GMTIME_R"] = True
        self._cmake.definitions["HAVE_LOCALTIME_R"] = self.settings.os != "Windows"
        self._cmake.definitions["HAVE_POSIX_FALLOCATE"] = not (self.settings.os in ["Windows", "Android"] or tools.is_apple_os(self.settings.os))
        self._cmake.definitions["HAVE_STRERROR_R"] = True
        self._cmake.definitions["HAVE_USLEEP"] = True
        self._cmake.definitions["DISABLE_GETHOSTUUID"] = self.options.disable_gethostuuid
        self._cmake.definitions["ENABLE_NULL_TRIM"] = self.options.enable_null_trim
        self._cmake.definitions["MAX_COLUMN"] = self.options.max_column
        self._cmake.configure()
        return self._cmake

    def build(self):
        cmake = self._configure_cmake()
        cmake.build()

    def package(self):
        header = tools.load(os.path.join(self._source_subfolder, "sqlite3.h"))
        license_content = header[3:header.find("***", 1)]
        tools.save(os.path.join(self.package_folder, "licenses", "LICENSE"), license_content)
        cmake = self._configure_cmake()
        cmake.install()

    def package_info(self):
        self.cpp_info.libs = tools.collect_libs(self)
        if self.settings.os == "Linux":
            if self.options.threadsafe:
                self.cpp_info.system_libs.append("pthread")
            if not self.options.omit_load_extension:
                self.cpp_info.system_libs.append("dl")
        if self.options.build_executable:
            bin_path = os.path.join(self.package_folder, "bin")
            self.output.info("Appending PATH env var with : {}".format(bin_path))
            self.env_info.PATH.append(bin_path)

        self.cpp_info.names["cmake_find_package"] = "SQLite3"
        self.cpp_info.names["cmake_find_package_multi"] = "SQLite3"
