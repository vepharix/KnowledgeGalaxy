import Lean
import KnowledgeGalaxy.PhaseTwoImports

open Lean

namespace KnowledgeGalaxy

structure FormalDependency where
  source : String
  target : String
  reference_kind : String
  occurrences : Nat
  deriving ToJson

private def nameFromString (value : String) : Name :=
  value.splitOn "." |>.foldl Name.str Name.anonymous

private def dependencyJson (scope : String) (dependencies : Array FormalDependency) : Json :=
  Json.mkObj [
    ("schema_version", toJson "knowledge-galaxy.lean-dependencies.1"),
    ("extractor", toJson "KnowledgeGalaxy Lean.Environment Expr.getUsedConstants"),
    ("toolchain", toJson "leanprover/lean4:v4.36.0-rc2"),
    ("source_revisions", Json.mkObj [
      ("lean-core", toJson "b35cb10cf2ced51a2fd1880cfdbf75c71ab7a35a"),
      ("mathlib", toJson "9bb5e306206014ecee5f033738bb5a6a8490d5c9")
    ]),
    ("extraction_scope", toJson scope),
    ("dependencies", toJson dependencies)
  ]

private def addReferences
    (target : Name)
    (kind : String)
    (expression : Expr)
    (dependencies : Array FormalDependency) : Array FormalDependency :=
  expression.getUsedConstants.foldl (init := dependencies) fun result source =>
    if source == target then result
    else result.push {
      source := source.toString
      target := target.toString
      reference_kind := kind
      occurrences := 1
    }

private def dependenciesFor (env : Environment) (target : Name) : Except String (Array FormalDependency) := do
  let some info := env.find? target
    | throw s!"declaration not found in imported environment: {target}"
  let dependencies := addReferences target "type_reference" info.type #[]
  let dependencies := match info.value? (allowOpaque := true) with
    | some value => addReferences target "value_reference" value dependencies
    | none => dependencies
  return dependencies

unsafe def extract (outputPath : System.FilePath) (scope : String) (targets : List String) : IO Unit := do
  if targets.isEmpty then
    throw <| IO.userError "at least one declaration name is required"
  let env ← importModules #[{ module := `KnowledgeGalaxy.PhaseTwoImports }] {} 0
  let mut dependencies := #[]
  for targetString in targets do
    let target := nameFromString targetString
    match dependenciesFor env target with
    | .ok found => dependencies := dependencies ++ found
    | .error message => throw <| IO.userError message
  let sortedDependencies := dependencies.qsort fun left right =>
    match compare left.target right.target with
    | .lt => true
    | .gt => false
    | .eq => match compare left.reference_kind right.reference_kind with
      | .lt => true
      | .gt => false
      | .eq => compare left.source right.source == .lt
  if let some parent := outputPath.parent then
    IO.FS.createDirAll parent
  IO.FS.writeFile outputPath (dependencyJson scope sortedDependencies).compress

end KnowledgeGalaxy
