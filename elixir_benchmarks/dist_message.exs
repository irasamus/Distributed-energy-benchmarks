defmodule PingPong do
  @total_messages 1_000_000

  def ponger_loop do
    receive do
      {:ping, sender_pid} ->
        # Send pong back to the sender
        send(sender_pid, :pong)
        ponger_loop()
    end
  end

  def run_worker do
    # Register the current process so it can be found by name
    Process.register(self(), :ponger_service)
    IO.puts("Worker (Ponger) UP and waiting for pings...")
    # ACTUALLY START THE LOOP
    ponger_loop()
  end

  def run_master(worker_node) do
    IO.puts("Connecting to #{worker_node}...")
    Node.connect(worker_node)

    # Address the remote process by {registered_name, node}
    target = {:ponger_service, worker_node}

    startTime = System.system_time(:millisecond)
    IO.puts("LOG_START:#{startTime}")

    # Send the first ping
    send(target, {:ping, self()})

    # Start the recursive receiving loop
    receive_loop(target, @total_messages - 1)

    endTime = System.system_time(:millisecond)
    IO.puts("LOG_END:#{endTime}")
    IO.puts("Total Time: #{endTime - startTime}ms")
    System.halt(0)
  end

  defp receive_loop(target, n) when n > 0 do
    receive do
      :pong ->
        # Optional: IO.puts("Pinger: Received pong, #{n} left")
        send(target, {:ping, self()})
        receive_loop(target, n - 1)
    end
  end

  defp receive_loop(_target, 0) do
    # Final wait for the last pong
    receive do
      :pong -> :ok
    end
  end
end

case System.argv() do
  ["worker"] -> PingPong.run_worker()
  ["master", node] -> PingPong.run_master(String.to_atom(node))
end
