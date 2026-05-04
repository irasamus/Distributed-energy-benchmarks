defmodule Trapezoid do
  @total_intervals 2_000_000_000
  @num_workers     100

  # Savina's actual function
  def fx(x) do
    (1.0 / (1.0 + :math.exp(:math.sqrt(2.0 * x)))) *
    :math.sin((:math.pow(x, 3) / (x + 1)) - 1.0)
  end

  def worker(master_pid, left, step, intervals) do
    area = perform_math(left, step, intervals, 0.0)
    send(master_pid, {:result, area})
  end

  defp perform_math(_x, _step, 0, acc), do: acc
  defp perform_math(x, step, count, acc) do
    new_area = (fx(x) + fx(x + step)) / 2.0 * step
    perform_math(x + step, step, count - 1, acc + new_area)
  end

  def run_worker do
    Process.sleep(:infinity)
  end

  def run_master(worker_nodes) do
    Enum.each(worker_nodes, &Node.connect/1)

    step = (100.0 - 1.0) / @total_intervals
    intervals_per_worker = div(@total_intervals, @num_workers)
    worker_node_list = Stream.cycle(worker_nodes) |> Enum.take(@num_workers)

    startTime = System.system_time(:millisecond)
    IO.puts("LOG_START:#{startTime}")

    worker_node_list |> Enum.with_index() |> Enum.each(fn {node, i} ->
      w_left = 1.0 + (i * intervals_per_worker * step)
      Node.spawn(node, Trapezoid, :worker, [self(), w_left, step, intervals_per_worker])
    end)

    collect_results(@num_workers, 0.0)

    endTime = System.system_time(:millisecond)
    IO.puts("LOG_END:#{endTime}")
    IO.puts("Total Time: #{endTime - startTime}ms")
    System.halt(0)
  end

  defp collect_results(0, total_area) do
    IO.puts("Result Area: #{total_area}")
  end
  defp collect_results(count, acc) do
    receive do
      {:result, area} -> collect_results(count - 1, acc + area)
    end
  end
end

case System.argv() do
  ["worker"]         -> Trapezoid.run_worker()
  ["master" | nodes] -> Trapezoid.run_master(Enum.map(nodes, &String.to_atom/1))
end
