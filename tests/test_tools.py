import unittest
import os
import shutil
import tempfile
from tools.base import ToolRegistry, ExecutionMode
from tools.system import ReadFileTool, ListDirTool, SearchGrepTool, WriteFileTool, PatchFileTool, ExecuteCommandTool

class TestToolPermissionsAndRegistry(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(ReadFileTool())
        self.registry.register(ListDirTool())
        self.registry.register(SearchGrepTool())
        self.registry.register(WriteFileTool())
        self.registry.register(PatchFileTool())
        self.registry.register(ExecuteCommandTool())
        
        # Set up a temp folder for executing file ops
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_get_tools_for_mode_plan(self):
        plan_tools = self.registry.get_tools_for_mode(ExecutionMode.PLAN)
        tool_names = [t.name for t in plan_tools]
        
        self.assertIn("read_file", tool_names)
        self.assertIn("list_dir", tool_names)
        self.assertIn("grep_search", tool_names)
        
        # Mutating tools must be omitted in PLAN mode
        self.assertNotIn("write_file", tool_names)
        self.assertNotIn("patch_file", tool_names)
        self.assertNotIn("execute_command", tool_names)

    def test_get_tools_for_mode_build(self):
        build_tools = self.registry.get_tools_for_mode(ExecutionMode.BUILD)
        self.assertEqual(len(build_tools), len(self.registry.all_tools))

    def test_safety_gate_denial(self):
        # Retrieving write_file tool in PLAN mode must fail
        with self.assertRaises(PermissionError):
            self.registry.get_tool("write_file", ExecutionMode.PLAN)

        # Retrieving in BUILD mode must succeed
        tool = self.registry.get_tool("write_file", ExecutionMode.BUILD)
        self.assertEqual(tool.name, "write_file")

    async def test_read_write_flow_in_build_mode(self):
        file_path = os.path.join(self.test_dir, "test.txt")
        write_tool = self.registry.get_tool("write_file", ExecutionMode.BUILD)
        
        # Perform write
        write_res = await write_tool.execute(path=file_path, content="Hello Unlocked AI!")
        self.assertIn("Successfully wrote file", write_res)
        
        # Perform read
        read_tool = self.registry.get_tool("read_file", ExecutionMode.PLAN)
        read_res = await read_tool.execute(path=file_path)
        self.assertEqual(read_res, "Hello Unlocked AI!")

    async def test_patch_flow_in_build_mode(self):
        file_path = os.path.join(self.test_dir, "test_patch.txt")
        write_tool = self.registry.get_tool("write_file", ExecutionMode.BUILD)
        await write_tool.execute(path=file_path, content="line 1\nline 2\nline 3")
        
        patch_tool = self.registry.get_tool("patch_file", ExecutionMode.BUILD)
        patch_res = await patch_tool.execute(
            path=file_path,
            target="line 2",
            replacement="patched line"
        )
        self.assertIn("Successfully patched", patch_res)
        
        read_tool = self.registry.get_tool("read_file", ExecutionMode.PLAN)
        read_res = await read_tool.execute(path=file_path)
        self.assertEqual(read_res, "line 1\npatched line\nline 3")

if __name__ == "__main__":
    unittest.main()
