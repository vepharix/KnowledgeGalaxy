import KnowledgeGalaxy.ExtractDependencies

unsafe def main (args : List String) : IO UInt32 := do
  match args with
  | outputPath :: scope :: targets =>
      KnowledgeGalaxy.extract outputPath scope targets
      return 0
  | _ =>
      IO.eprintln "usage: extract-dependencies OUTPUT_PATH SCOPE DECLARATION..."
      return 2
