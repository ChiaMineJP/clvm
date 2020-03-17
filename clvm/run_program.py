from .casts import limbs_for_int
from .EvalError import EvalError

QUOTE_COST = 1
ARGS_COST = 1
SHIFT_COST_PER_LIMB = 1


def run_program(
    program,
    args,
    quote_kw,
    args_kw,
    operator_lookup,
    max_cost=None,
    pre_eval_op=None,
):

    def eval_atom_op(op_stack, value_stack):
        pair = value_stack.pop()
        sexp = pair.first()
        env = pair.rest()
        node_index = sexp.as_int()
        cost = 1
        while node_index > 1:
            if node_index & 1:
                env = env.rest()
            else:
                env = env.first()
            cost += SHIFT_COST_PER_LIMB * limbs_for_int(node_index)
            node_index >>= 1
        value_stack.append(env)
        return cost

    def swap_op(op_stack, value_stack):
        v2 = value_stack.pop()
        v1 = value_stack.pop()
        value_stack.append(v2)
        value_stack.append(v1)
        return 0

    def cons_op(op_stack, value_stack):
        v1 = value_stack.pop()
        v2 = value_stack.pop()
        value_stack.append(v1.cons(v2))
        return 0

    def eval_op(op_stack, value_stack):
        if pre_eval_op:
            pre_eval_op(op_stack, value_stack)

        pair = value_stack.pop()
        sexp = pair.first()
        args = pair.rest()

        # put a bunch of ops on op_stack

        if not sexp.listp():
            # sexp is an atom
            op_stack.append(eval_atom_op)
            value_stack.append(pair)
            return 1

        operator = sexp.first()
        if operator.listp():
            value_stack.append(operator.cons(args))
            op_stack.append(eval_op)
            op_stack.append(eval_op)
            return 1

        op = operator.as_atom()
        operand_list = sexp.rest()
        if op == quote_kw:
            if operand_list.nullp() or not operand_list.rest().nullp():
                raise EvalError("quote requires exactly 1 parameter", sexp)
            value_stack.append(operand_list.first())
            return QUOTE_COST

        if op == args_kw:
            if sexp.nullp() or not sexp.rest().nullp():
                raise EvalError("env requires no parameters", sexp)
            value_stack.append(args)
            return ARGS_COST

        op_stack.append(apply_op)
        value_stack.append(operator)
        for _ in operand_list.as_iter():
            value_stack.append(_.cons(args))
            op_stack.append(cons_op)
            op_stack.append(eval_op)
            op_stack.append(swap_op)
        value_stack.append(operator.null())
        return 1

    def apply_op(op_stack, value_stack):
        operand_list = value_stack.pop()
        operator = value_stack.pop()
        if operator.listp():
            raise EvalError("internal error", operator)

        f = operator_lookup.get(operator.as_atom())
        if f:
            additional_cost, r = f(operand_list)
            value_stack.append(r)
            return additional_cost

        raise EvalError("unimplemented operator", operator)

    op_stack = [eval_op]
    value_stack = [program.cons(args)]
    cost = 0

    while op_stack:
        f = op_stack.pop()
        cost += f(op_stack, value_stack)
        if max_cost and cost > max_cost:
            raise EvalError("cost exceeded", value_stack[-1])
    return cost, value_stack[-1]
