defmodule PingPong do
  @total_messages 10_000_000

  def ponger_loop do
    receive do
      {:ping, sender_pid} ->
        send(sender_pid, :pong)
        ponger_loop()
    end
  end

  def run_worker do
    Process.register(self(), :ponger_service)
    IO.puts("Worker (Ponger) UP")
    Process.sleep(:infinity)
  end

  def run_master(worker_node) do
    Node.connect(worker_node)
    target = {:ponger_service, worker_node}

    startTime = System.system_time(:millisecond)
    IO.puts("LOG_START:#{startTime}")

    send(target, {:ping, self()})
    receive_loop(target, @total_messages - 1)

    endTime = System.system_time(:millisecond)
    IO.puts("LOG_END:#{endTime}")
    System.halt(0)
  end

  defp receive_loop(target, n) when n > 0 do
    receive do
      :pong ->
        if rem(n, 1000000) == 0, do: IO.puts("Remaining: #{n}")
        send(target, {:ping, self()})
        receive_loop(target, n - 1)
    end
  end
  defp receive_loop(_target, 0) do
    receive do :pong -> :ok end
  end
end

case System.argv() do
  ["worker"] -> PingPong.run_worker()
  ["master", node] -> PingPong.run_master(String.to_atom(node))
end
