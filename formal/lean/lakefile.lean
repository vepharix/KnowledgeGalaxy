import Lake
open Lake DSL

package «knowledge-galaxy-lean» where
  version := v!"0.1.0"

require mathlib from git
  "https://github.com/leanprover-community/mathlib4" @
  "9bb5e306206014ecee5f033738bb5a6a8490d5c9"

lean_lib KnowledgeGalaxy where

@[default_target]
lean_exe «extract-dependencies» where
  root := `Main
