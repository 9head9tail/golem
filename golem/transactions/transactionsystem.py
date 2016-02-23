import logging
import datetime

from paymentskeeper import PaymentInfo, PaymentsKeeper
from incomeskeeper import IncomesKeeper
from golem.model import Bank
from golem.core.variables import PRICE_BASE

logger = logging.getLogger(__name__)


class TransactionSystem(object):
    """ Transaction system. Keeps information about budget, expected payments, etc. """

    def __init__(self, node_id, payments_keeper_class=PaymentsKeeper):
        """ Create new transaction system instance for node with given id
        :param node_id: id of a node that has this transaction system
        :param payments_keeper_class: default PaymentsKeeper, payment keeper class, an instance of this class
        while be used as a payment keeper
        """
        self.node_id = node_id
        self.payments_keeper = payments_keeper_class(node_id)  # Keeps information about payments to send
        self.incomes_keeper = IncomesKeeper(node_id)  # Keeps information about received payments
        self.budget = Bank.get(Bank.node_id == node_id).val  # Current budget state
        self.price_base = PRICE_BASE  # Price base for price modifications

    # TODO Powinno isc jakies info do payment keepera
    def task_reward_paid(self, task_id, price):
        """ Inform that payment succeeded. New bank account may be permanently saved.
        :param task_id: payment for this task has succeeded
        :param int price: payment for price with that heigh has succeeded
        """
        Bank.update(val=self.budget, modified_date=str(datetime.datetime.now())).where(
            Bank.node_id == self.node_id).execute()

    # TODO Powinno dzialac tez dla subtask id
    # Price tu chyba nie potrzebne tylko powinno byc pobierane z payment keepera
    def task_reward_payment_failure(self, task_id, price):
        """ Inform payment keeper about payment failure. If it keeps information about payments for this subtask it
        should be removed. Specific amount should also return to the budget.
        :param task_id: payment for task with this id has failed
        :param int price:
        """
        self.budget += price
        self.payments_keeper.payment_failure(task_id)

    def get_reward(self, task_id, node_id, reward):
        """ Increase information about budget with reward
        :param task_id: return id of a task for which this reward was
        :param int reward: how much should be added to budget
        """
        self.budget += reward
        Bank.update(val=self.budget, modified_date=str(datetime.datetime.now())).where(
            Bank.node_id == self.node_id).execute()
        self.incomes_keeper.add_income(task_id, node_id, reward)

    def add_payment_info(self, task_id, subtask_id, price_mod, account_info):
        """ Add to payment keeper information about new payment for subtask
        :param task_id: id of a task that this payment is apply to
        :param subtask_id: if of a subtask that this payment is apply to (node finished computation for that subtask)
        :param float price_mod: valuation of a given subtask
        :param AccountInfo account_info: billing account for a node that has computed a task
        """
        price = self.count_price(price_mod)
        payment_info = PaymentInfo(task_id, subtask_id, price, account_info)
        self.payments_keeper.finished_subtasks(payment_info)

    def task_finished(self, task_id):
        """ Inform payments keeper that task with given id has been finished and payments for that task may be
        appraise.
        :param task_id: id of a finished task
        """
        self.payments_keeper.task_finished(task_id)

    def get_new_payments_tasks(self):
        """ Return new payment for a computed task that hasn't been processed yet.
        :return tuple: return task id and list of payments for this task or a pair with two None
        """
        task, payments = self.payments_keeper.get_new_payments_task(self.budget)
        if task is None:
            return None, None
        if self.budget >= task.value:
            self.budget -= task.value
            return task.task_id, payments
        else:
            self.payments_keeper.payment_failure(task.task_id)
            logger.warning("Can't paid for the task, not enough money")
            return None, None

    def count_price(self, price_mod):
        """ Count price for a task based on base price and given price mod
        :param float price_mod: price modification that should be used to count real price for task
        :return int: price that should be paid for a task
        """
        return int(round(price_mod * self.price_base))

    def get_payments_list(self):
        """ Return list of all planned and made payments
        :return list: list of dictionaries describing payments
        """
        return self.payments_keeper.get_list_of_all_payments()

    def get_incomes_list(self):
        """ Return list of all expected and received incomes
        :return list: list of dictionaries describing incomes
        """
        return self.incomes_keeper.get_list_of_all_incomes()

    def add_to_waiting_payments(self, task_id, node_id):
        return self.incomes_keeper.add_waiting_payment(task_id, node_id)

    def add_to_timeouted_payments(self, task_id):
        return self.incomes_keeper.add_timeouted_payment(task_id)