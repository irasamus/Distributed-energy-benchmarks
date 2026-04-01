defmodule DistSpawner do
  @total_actors 1_000_000

  def worker_task(parent) do
    send(parent, :done)
  end

  def run_master(worker_node) do
    # Connect to the remote Grid'5000 node
    Node.connect(worker_node)

    startTime = System.system_time(:millisecond)
    IO.puts("LOG_START:#{startTime}")

    Enum.each(1..@total_actors, fn i ->
      Node.spawn(worker_node, DistSpawner, :worker_task, [self()])
      receive do :done -> :ok end

      if rem(i, 50000) == 0 do
        IO.puts("Progress: #{i} / #{@total_actors}")
      end
    end)

    endTime = System.system_time(:millisecond)
    IO.puts("LOG_END:#{endTime}")
    System.halt(0)
  end
end

case System.argv() do
  ["worker"] ->
    IO.puts("Worker ready.")
    Process.sleep(:infinity)
  ["master", node] ->
    DistSpawner.run_master(String.to_atom(node))
end
