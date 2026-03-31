defmodule Trapezoid do
  @moduledoc """
  Distributed Trapezoidal Approximation matching Akka TrapezoidRun.java logic.
  """

  # --- 1. MATHEMATICAL FUNCTION ---
  def fx(x) do
    :math.sin(x) * :math.cos(x) * :math.sqrt(x)
  end

  # --- 2. WORKER LOGIC (Nodes B and C) ---
  def worker_loop do
    receive do
      {:work, left, right, step, intervals, reply_to} ->
        IO.puts("Computing range: #{left} to #{right}")

        # Perform the trapezoidal math
        area = perform_math(left, step, intervals, 0.0)

        # Send result back to Master
        send(reply_to, {:result, area})
        worker_loop()
    end
  end

  # Recursive math function (Optimized for Elixir/BEAM)
  defp perform_math(_x, _step, 0, acc), do: acc
  defp perform_math(x, step, count, acc) do
    # Trapezoidal rule: (f(x) + f(x+step)) / 2 * step
    new_area = (fx(x) + fx(x + step)) / 2.0 * step
    perform_math(x + step, step, count - 1, acc + new_area)
  end

  def run_worker do
    # Register the worker so the Master can find it by name
    Process.register(self(), :trapezoid_worker)
    IO.puts("Worker Node is UP and registered as :trapezoid_worker")
    worker_loop()
  end

  # --- 3. MASTER LOGIC (Node A) ---
  def run_master(worker_nodes, total_intervals) do
    # Ensure all nodes are connected
    Enum.each(worker_nodes, &Node.connect/1)

    num_workers = length(worker_nodes)
    left_boundary = 1.0
    right_boundary = 100.0
    step = (right_boundary - left_boundary) / total_intervals
    intervals_per_worker = div(total_intervals, num_workers)

    # We start the timer here
    startTime = System.system_time(:millisecond)
    IO.puts("Found #{num_workers} workers. Starting calculation...")
    IO.puts("LOG_START:#{startTime}")

    # Delegate work to all nodes in parallel
    worker_nodes
    |> Enum.with_index()
    |> Enum.each(fn {node, i} ->
      w_left = left_boundary + (i * intervals_per_worker * step)
      w_right = w_left + (intervals_per_worker * step)

      # Target the named process on the remote node
      target = {:trapezoid_worker, node}
      send(target, {:work, w_left, w_right, step, intervals_per_worker, self()})
    end)

    # Collect results
    total_area = collect_results(num_workers, 0.0)

    endTime = System.system_time(:millisecond)
    IO.puts("LOG_END:#{endTime}")
    IO.puts("Result Area: #{total_area}")
    IO.puts("Total Time: #{endTime - startTime} ms")

    System.halt(0)
  end

  defp collect_results(0, acc), do: acc
  defp collect_results(count, acc) do
    receive do
      {:result, area} ->
        collect_results(count - 1, acc + area)
    end
  end
end

# --- 4. COMMAND LINE HANDLER ---
case System.argv() do
  ["worker"] ->
    Trapezoid.run_worker()
  ["master" | nodes] ->
    # The last argument is the total intervals, the others are node names
    {count_str, node_list} = List.pop_at(nodes, -1)
    worker_nodes = Enum.map(node_list, &String.to_atom/1)
    Trapezoid.run_master(worker_nodes, String.to_integer(count_str))
  _ ->
    IO.puts("Usage: elixir dist_trapezoid.exs [worker|master] [node_names...] [interval_count]")
end
