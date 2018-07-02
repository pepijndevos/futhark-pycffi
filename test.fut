entry test1 (a:f32) : f32 =
  a+1

entry test2 (a: []i32) : i32 =
  reduce (+) 0 a

entry test3 (a: []i32) : []i32 =
  scan (+) 0 a

entry test4 (a:f32) (b:f32) : (f32, f32) =
  (a+b, a-b)

entry test5 (a:[][]u64) : [][]u64 =
  map (map (*2)) a
