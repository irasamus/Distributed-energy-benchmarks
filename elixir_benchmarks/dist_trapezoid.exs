defmodule Trapezoid do
  @total_intervals 1_000_000_000

  def fx(x), do: :math.sin(x) * :math.cos(x) * :math.sqrt(x)

  def worker_loop do
    receive do
      {:work, left, step, intervals, reply_to} ->
        area = perform_math(left, step, intervals, 0.0)
        send(reply_to, {:result, area})
        worker_loop()
    end
  end

  defp perform_math(_x, _step, 0, acc), do: acc
  defp perform_math(x, step, count, acc) do
    new_area = (fx(x) + fx(x + step)) / 2.0 * step
    perform_math(x + step, step, count - 1, acc + new_area)
  end

  def run_worker do
    Process.register(self(), :trapezoid_worker)
    IO.puts("Worker UP")
    Process.sleep(:infinity)
  end

  def run_master(worker_nodes) do
    Enum.each(worker_nodes, &Node.connect/1)
    num_workers = length(worker_nodes)
    step = (100.0 - 1.0) / @total_intervals
    intervals_per_worker = div(@total_intervals, num_workers)

    startTime = System.system_time(:millisecond)
    IO.puts("LOG_START:#{startTime}")

    worker_nodes |> Enum.with_index() |> Enum.each(fn {node, i} ->
      w_left = 1.0 + (i * intervals_per_worker * step)
      send({:trapezoid_worker, node}, {:work, w_left, step, intervals_per_worker, self()})
    end)

    collect_results(num_workers, 0.0)
    endTime = System.system_time(:millisecond)
    IO.puts("LOG_END:#{endTime}")
    System.halt(0)
  end

  defp collect_results(0, _acc), do: :ok
  defp collect_results(count, acc) do
    receive do {:result, area} -> collect_results(count - 1, acc + area) end
  end
end

case System.argv() do
  ["worker"] -> Trapezoid.run_worker()
  ["master" | nodes] -> Trapezoid.run_master(Enum.map(nodes, &String.to_atom/1))
end
