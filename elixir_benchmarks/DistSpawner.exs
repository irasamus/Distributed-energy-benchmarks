defmodule DistSpawner do
  def worker_task(parent) do
    # Simply tell the master we are done
    send(parent, :done)
  end

  def run_master(worker_node, total_actors) do
    # Ensure the nodes are actually connected before starting
    if Node.connect(worker_node) do
      IO.puts("Connected to #{worker_node}")

      startTime = System.system_time(:millisecond)
      IO.puts("LOG_START:#{startTime}")

      # SEQUENTIAL LOOP: Matches Akka SpawnRunner
      Enum.each(1..total_actors, fn i ->
        # 1. Trigger remote spawn
        Node.spawn(worker_node, DistSpawner, :worker_task, [self()])

        # 2. Wait for the ':done' reply before doing the next one
        receive do
          :done -> :ok
        end

        # Progress logging every 5000 (just like Akka)
        if rem(i, 5000) == 0 do
          IO.puts("Spawned: #{i} / #{total_actors}")
        end
      end)

      endTime = System.system_time(:millisecond)
      IO.puts("LOG_END:#{endTime}")
      IO.puts("Total time for #{total_actors} sequential spawns: #{endTime - startTime}ms")
    else
      IO.puts("Error: Could not connect to #{worker_node}")
    end

    System.halt(0)
  end
end

case System.argv() do
  ["worker"] ->
    IO.puts("Worker node ready.")
    Process.sleep(:infinity)
  ["master", node, count] ->
    DistSpawner.run_master(String.to_atom(node), String.to_integer(count))
end
