defmodule PingPong do
  @moduledoc """
  Distributed Ping-Pong benchmark designed to match Akka MessageRun.java
  """

  # --- 1. THE PONGER (Node B) ---
  def ponger_loop do
    receive do
      {:ping, sender_pid} ->
        send(sender_pid, :pong)
        ponger_loop()
    end
  end

  def run_worker do
    # Register the process locally so Node A can find it by name
    Process.register(self(), :ponger_service)
    IO.puts("Worker (Ponger) is UP and registered as :ponger_service")
    ponger_loop()
  end

  # --- 2. THE PINGER (Node A) ---
  def run_master(worker_node, n) do
    # Ensure nodes are connected (Grid'5000 requirement)
    Node.connect(worker_node)

    # In Elixir, we can address a remote process as {name, node}
    # This is the equivalent of an Akka ActorRef found via Receptionist
    target = {:ponger_service, worker_node}

    startTime = System.system_time(:millisecond)
    IO.puts("LOG_START:#{startTime}")

    # Kick off the first ping
    send(target, {:ping, self()})

    # Enter the message loop
    receive_loop(target, n - 1)

    endTime = System.system_time(:millisecond)
    IO.puts("LOG_END:#{endTime}")
    IO.puts("Total Time: #{endTime - startTime}ms")

    # Kill the master process when done
    System.halt(0)
  end

  defp receive_loop(target, n) when n > 0 do
    receive do
      :pong ->
        send(target, {:ping, self()})
        receive_loop(target, n - 1)
    end
  end

  defp receive_loop(_target, 0) do
    # Wait for the very last pong before finishing
    receive do
      :pong -> :ok
    end
  end
end

# --- 3. COMMAND LINE HANDLER ---
case System.argv() do
  ["worker"] ->
    PingPong.run_worker()
  ["master", node, count] ->
    PingPong.run_master(String.to_atom(node), String.to_integer(count))
  _ ->
    IO.puts("Usage: elixir dist_message.exs [worker|master] [node_name] [count]")
end
